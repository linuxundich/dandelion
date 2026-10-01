# SPDX-License-Identifier: GPL-3.0-or-later
"""X (ehemals Twitter) über die API v2.

Login: OAuth 2.0 mit PKCE über eine eigene Developer-App (Typ „Native App“,
öffentlicher Client). X rechnet pro Aufruf ab; die Kosten trägt das Konto
der Developer-App, also der Nutzer selbst.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.parse
from gettext import gettext as _
from typing import Any

from ..auth.oauth import Pkce, new_state
from ..core import imaging
from ..core.counting import find_urls, x_count
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

API = "https://api.x.com"
AUTHORIZE = "https://x.com/i/oauth2/authorize"
IMAGE_MAX = 5_000_000
COST_POST = 0.015
COST_POST_URL = 0.20


def _money(value: float, digits: int) -> str:
    """Betrag in Dollar im Zahlenformat der Systemsprache."""
    import locale
    try:
        number = locale.format_string(f"%.{digits}f", value)
    except ValueError:
        number = f"{value:.{digits}f}"
    return f"{number} $"


class X(AppPlatform):
    id = "x"
    name = "X"
    style_class = "platform-x"
    client_secret_mode = "optional"
    portal_url = "https://developer.x.com/en/portal/dashboard"
    scopes = "tweet.read tweet.write users.read media.write offline.access"

    def default_limits(self) -> PlatformLimits:
        return PlatformLimits(
            max_chars=280,
            url_weight=23,
            max_images=4,
            max_videos=1,
            allow_mixed_media=False,
            image_mime_types=("image/jpeg", "image/png", "image/gif", "image/webp"),
            video_mime_types=("video/mp4",),
            max_image_bytes=None,       # größere Bilder werden verkleinert
            max_video_bytes=0,          # Video folgt später
            alt_text_max=1000,
            supports_threads=True,
            client_link_card=False,
        )

    def count(self, comp: Composition, limits: PlatformLimits) -> Count:
        return Count(x_count(comp.text), limits.max_chars)

    @staticmethod
    def post_cost(text: str) -> float:
        return COST_POST_URL if find_urls(text) else COST_POST

    def cost_notice(self, comp: Composition) -> str | None:
        if find_urls(comp.text):
            return _("X charges your developer account about {cost} for this post because it "
                     "contains a link.").format(cost=_money(COST_POST_URL, 2))
        return _("X charges your developer account about {cost} for this post.").format(
            cost=_money(COST_POST, 3))

    # -- Login -------------------------------------------------------------
    def begin_app_login(self, client_id: str, client_secret: str) -> AppLogin:
        pkce = Pkce.create()
        state = new_state()
        q = urllib.parse.urlencode({
            "response_type": "code", "client_id": client_id.strip(),
            "redirect_uri": self.redirect_uri, "scope": self.scopes, "state": state,
            "code_challenge": pkce.challenge, "code_challenge_method": pkce.method,
        })
        return AppLogin(self.id, f"{AUTHORIZE}?{q}", self.redirect_uri, state,
                        client_id.strip(), client_secret.strip(), pkce.verifier)

    def _token_request(self, client_id: str, client_secret: str,
                       form: dict[str, str]) -> Request:
        headers: dict[str, str] = {}
        if client_secret:
            # Vertraulicher Client: Basic-Auth statt client_id im Formular
            raw = f"{client_id}:{client_secret}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
        else:
            form = {**form, "client_id": client_id}
        return Request("POST", f"{API}/2/oauth2/token", form=form, headers=headers)

    async def complete_app_login(self, login: AppLogin,
                                 code: str) -> list[tuple[Profile, dict[str, Any]]]:
        resp = await self._send(self._token_request(login.client_id, login.client_secret, {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": login.redirect_uri, "code_verifier": login.verifier}))
        tok = resp.json()
        secret = self._secret_from_token(tok, login.client_id, login.client_secret)
        me = (await self._send(Request(
            "GET", f"{API}/2/users/me", params={"user.fields": "profile_image_url,name"},
            headers={"Authorization": f"Bearer {secret['access_token']}"}))).json()["data"]
        profile = Profile(platform=self.id, remote_id=str(me["id"]), handle=me["username"],
                          display_name=me.get("name", ""),
                          avatar_url=me.get("profile_image_url"), auth_method="byo-oauth")
        return [(profile, secret)]

    @staticmethod
    def _secret_from_token(tok: dict[str, Any], client_id: str,
                           client_secret: str) -> dict[str, Any]:
        return {"access_token": tok["access_token"],
                "refresh_token": tok.get("refresh_token", ""),
                "expires_at": time.time() + float(tok.get("expires_in", 7200)),
                "client_id": client_id, "client_secret": client_secret}

    async def _access_token(self, profile: Profile) -> str:
        data = await self._token_data(profile)
        if float(data.get("expires_at", 0)) > time.time() + 60:
            return str(data["access_token"])
        if not data.get("refresh_token"):
            raise PlatformError(_("The login has expired. Please sign in again."), auth=True)
        resp = await self._send(self._token_request(
            data["client_id"], data.get("client_secret", ""),
            {"grant_type": "refresh_token", "refresh_token": data["refresh_token"]}))
        new = self._secret_from_token(resp.json(), data["client_id"],
                                      data.get("client_secret", ""))
        if not new["refresh_token"]:
            new["refresh_token"] = data["refresh_token"]
        await self.store_credentials(profile, new)
        return str(new["access_token"])

    def _error(self, resp: Response) -> PlatformError:
        detail = resp.text()[:400]
        try:
            body = resp.json() or {}
            msg = body.get("detail") or body.get("title") or ""
        except ValueError:
            msg = ""
        if resp.status == 402:
            return PlatformError(_("Your X developer account has no credits left. Top up "
                                   "credits in the X developer console."), detail)
        if resp.status == 403:
            return PlatformError(_("X refused the request: {reason}").format(
                reason=msg or _("not permitted")), detail)
        if resp.status == 401:
            return PlatformError(_("The login has expired. Please sign in again."), detail,
                                 auth=True)
        err = error_from_status(resp.status, detail)
        if resp.status == 400 and msg:
            err.message = _("X rejected the post: {reason}").format(reason=msg)
        return err

    async def _api(self, profile: Profile, method: str, path: str, **kw: Any) -> Response:
        token = await self._access_token(profile)
        headers = {"Authorization": f"Bearer {token}", **kw.pop("headers", {})}
        return await self._send(Request(method, f"{API}{path}", headers=headers, **kw))

    # -- Netzwerk ----------------------------------------------------------
    async def refresh_profile(self, profile: Profile) -> Profile:
        try:
            me = (await self._api(profile, "GET", "/2/users/me",
                                  params={"user.fields": "profile_image_url,name"})).json()
        except PlatformError as e:
            profile.status = ProfileStatus.EXPIRED if e.auth else ProfileStatus.ERROR
            profile.status_detail = e.message
            return profile
        data = me.get("data", {})
        profile.handle = data.get("username", profile.handle)
        profile.display_name = data.get("name", profile.display_name)
        profile.avatar_url = data.get("profile_image_url", profile.avatar_url)
        profile.status = ProfileStatus.OK
        profile.status_detail = ""
        profile.limits_json = self.default_limits().to_json()
        profile.limits_fetched_at = now_iso()
        return profile

    async def upload_media(self, profile: Profile, media: Media) -> str:
        if not media.is_image:
            raise PlatformError(_("Videos are not supported for X yet."))
        data = imaging.load_bytes(media.path)
        mime = media.mime
        if len(data) > IMAGE_MAX or mime not in ("image/jpeg", "image/png", "image/webp",
                                                  "image/gif"):
            data, mime, _w, _h = imaging.shrink_to(data, IMAGE_MAX)
        category = "tweet_gif" if mime == "image/gif" else "tweet_image"
        resp = await self._api(profile, "POST", "/2/media/upload",
                               form={"media_category": category},
                               files=[FilePart("media", os.path.basename(media.path), mime, data)],
                               timeout=300)
        body = resp.json() or {}
        media_id = str((body.get("data") or {}).get("id") or body.get("media_id_string"))
        if media.alt_text.strip():
            await self._api(profile, "POST", "/2/media/metadata", json={
                "id": media_id, "metadata": {"alt_text": {"text": media.alt_text.strip()}}})
        return json.dumps({"id": media_id})

    async def post(self, profile: Profile, comp: Composition, media_refs: list[str], *,
                   reply_to: TargetPart | None, root: TargetPart | None,
                   idempotency_key: str) -> TargetPart:
        payload: dict[str, Any] = {"text": comp.text}
        if media_refs:
            payload["media"] = {"media_ids": [json.loads(r)["id"] for r in media_refs]}
        if reply_to and reply_to.remote_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to.remote_id}
        data = (await self._api(profile, "POST", "/2/tweets", json=payload)).json()["data"]
        tweet_id = str(data["id"])
        return TargetPart(idx=0, remote_id=tweet_id,
                          remote_url=f"https://x.com/{profile.handle}/status/{tweet_id}")

    async def delete(self, profile: Profile, part: TargetPart) -> None:
        if part.remote_id:
            await self._api(profile, "DELETE", f"/2/tweets/{part.remote_id}")

    async def logout(self, profile: Profile) -> None:
        data = await self.secrets.get(profile.uuid, "oauth")
        if data and data.get("access_token"):
            req = self._token_request(data["client_id"], data.get("client_secret", ""), {
                "token": data["access_token"], "token_type_hint": "access_token"})
            req.url = f"{API}/2/oauth2/revoke"
            try:
                await self._send(req)
            except PlatformError:
                pass
        await super().logout(profile)
