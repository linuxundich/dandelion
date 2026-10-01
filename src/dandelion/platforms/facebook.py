# SPDX-License-Identifier: GPL-3.0-or-later
"""Facebook-Seiten über die Graph API.

Per API lassen sich nur Seiten bespielen, keine privaten Profile und keine
Gruppen. Login über eine eigene Meta-App im Entwicklungsmodus (der Nutzer
ist Admin, dann ist kein App Review nötig). Im Entwicklungsmodus erlaubt
Meta `http://localhost` als Redirect, deshalb reicht der Systembrowser.

Token-Kette: Code → kurzlebiges User-Token → Langzeit-User-Token →
Seiten-Token ohne Ablauf.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from gettext import gettext as _
from typing import Any

from ..auth.oauth import new_state
from ..core import imaging
from ..core.counting import find_urls, generic_count
from ..core.models import Media, Profile, ProfileStatus, TargetPart, now_iso
from ..net.http import FilePart, Request, Response
from .base import (
    AppLogin,
    AppPlatform,
    Composition,
    Count,
    PlatformError,
    PlatformLimits,
    error_from_status,
)

GRAPH_VERSION = "v26.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
DIALOG = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
IMAGE_MAX = 4_000_000


class Facebook(AppPlatform):
    id = "facebook"
    name = "Facebook"
    style_class = "platform-facebook"
    client_secret_mode = "required"
    redirect_host = "localhost"
    portal_url = "https://developers.facebook.com/apps/"
    scopes = "pages_show_list,pages_manage_posts,pages_read_engagement"

    def default_limits(self) -> PlatformLimits:
        return PlatformLimits(
            max_chars=63_206,
            max_images=10,
            max_videos=1,
            allow_mixed_media=False,
            image_mime_types=("image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff"),
            video_mime_types=("video/mp4",),
            max_image_bytes=None,       # größere Bilder werden verkleinert
            max_video_bytes=0,          # Video folgt später
            alt_text_max=None,
            supports_threads=False,
            client_link_card=False,
            preview_truncate=480,
        )

    def count(self, comp: Composition, limits: PlatformLimits) -> Count:
        return Count(generic_count(comp.text), limits.max_chars)

    # -- Login -------------------------------------------------------------
    def begin_app_login(self, client_id: str, client_secret: str) -> AppLogin:
        state = new_state()
        q = urllib.parse.urlencode({
            "client_id": client_id.strip(), "redirect_uri": self.redirect_uri,
            "state": state, "response_type": "code", "scope": self.scopes})
        return AppLogin(self.id, f"{DIALOG}?{q}", self.redirect_uri, state,
                        client_id.strip(), client_secret.strip())

    async def complete_app_login(self, login: AppLogin,
                                 code: str) -> list[tuple[Profile, dict[str, Any]]]:
        short = (await self._send(Request("GET", f"{GRAPH}/oauth/access_token", params={
            "client_id": login.client_id, "client_secret": login.client_secret,
            "redirect_uri": login.redirect_uri, "code": code}))).json()["access_token"]
        long_lived = (await self._send(Request("GET", f"{GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": login.client_id,
            "client_secret": login.client_secret,
            "fb_exchange_token": short}))).json()["access_token"]
        pages = (await self._send(Request("GET", f"{GRAPH}/me/accounts", params={
            "fields": "id,name,access_token,picture{url},tasks",
            "access_token": long_lived}))).json().get("data", [])
        result = []
        for page in pages:
            tasks = page.get("tasks") or []
            if tasks and "CREATE_CONTENT" not in tasks:
                continue
            profile = Profile(platform=self.id, remote_id=str(page["id"]), handle=page["name"],
                              display_name=page["name"],
                              avatar_url=((page.get("picture") or {}).get("data") or {}).get("url"),
                              auth_method="byo-oauth")
            result.append((profile, {"access_token": page["access_token"],
                                     "client_id": login.client_id}))
        if not result:
            raise PlatformError(_("No Facebook page was found that you are allowed to post "
                                  "to. Posting to personal profiles is not possible."))
        return result

    # -- Hilfen ------------------------------------------------------------
    def _error(self, resp: Response) -> PlatformError:
        detail = resp.text()[:400]
        try:
            err = (resp.json() or {}).get("error", {})
        except ValueError:
            err = {}
        code, msg = err.get("code"), err.get("message", "")
        if code == 190 or resp.status == 401:
            return PlatformError(_("The Facebook login is no longer valid. Please sign in "
                                   "again."), detail, auth=True)
        if code in (10, 200) or (isinstance(code, int) and 200 <= code < 300):
            return PlatformError(_("Facebook denied the permission: {reason}").format(
                reason=msg), detail)
        if code in (4, 17, 32, 613):
            return PlatformError(_("Too many requests. Please try again later."), detail,
                                 retryable=True)
        out = error_from_status(resp.status, detail)
        if msg and resp.status == 400:
            out.message = _("Facebook rejected the post: {reason}").format(reason=msg)
        return out

    async def _graph(self, profile: Profile, method: str, path: str, **kw: Any) -> Response:
        data = await self._token_data(profile)
        if method == "GET" or method == "DELETE":
            kw["params"] = {**(kw.get("params") or {}), "access_token": data["access_token"]}
        else:
            kw["form"] = {**(kw.get("form") or {}), "access_token": data["access_token"]}
        return await self._send(Request(method, f"{GRAPH}{path}", **kw))

    # -- Netzwerk ----------------------------------------------------------
    async def refresh_profile(self, profile: Profile) -> Profile:
        try:
            page = (await self._graph(profile, "GET", f"/{profile.remote_id}",
                                      params={"fields": "name,picture{url}"})).json()
        except PlatformError as e:
            profile.status = ProfileStatus.EXPIRED if e.auth else ProfileStatus.ERROR
            profile.status_detail = e.message
            return profile
        profile.handle = profile.display_name = page.get("name", profile.handle)
        profile.avatar_url = ((page.get("picture") or {}).get("data") or {}).get(
            "url", profile.avatar_url)
        profile.status = ProfileStatus.OK
        profile.status_detail = ""
        profile.limits_json = self.default_limits().to_json()
        profile.limits_fetched_at = now_iso()
        return profile

    async def upload_media(self, profile: Profile, media: Media) -> str:
        if not media.is_image:
            raise PlatformError(_("Videos are not supported for Facebook yet."))
        data = imaging.load_bytes(media.path)
        mime = media.mime
        if len(data) > IMAGE_MAX:
            data, mime, _w, _h = imaging.shrink_to(data, IMAGE_MAX)
        form: dict[str, Any] = {"published": "false"}
        if media.alt_text.strip():
            form["alt_text_custom"] = media.alt_text.strip()
        resp = await self._graph(profile, "POST", f"/{profile.remote_id}/photos", form=form,
                                 files=[FilePart("source", os.path.basename(media.path),
                                                 mime, data)], timeout=300)
        return json.dumps({"media_fbid": str(resp.json()["id"])})

    async def post(self, profile: Profile, comp: Composition, media_refs: list[str], *,
                   reply_to: TargetPart | None, root: TargetPart | None,
                   idempotency_key: str) -> TargetPart:
        form: dict[str, Any] = {"message": comp.text}
        if media_refs:
            for i, ref in enumerate(media_refs):
                form[f"attached_media[{i}]"] = ref
        else:
            urls = find_urls(comp.text)
            if urls:
                form["link"] = urls[0].value
        post_id = str((await self._graph(profile, "POST", f"/{profile.remote_id}/feed",
                                         form=form)).json()["id"])
        return TargetPart(idx=0, remote_id=post_id,
                          remote_url=f"https://www.facebook.com/{post_id}")

    async def delete(self, profile: Profile, part: TargetPart) -> None:
        if part.remote_id:
            await self._graph(profile, "DELETE", f"/{part.remote_id}")
