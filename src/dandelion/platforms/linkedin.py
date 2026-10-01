# SPDX-License-Identifier: GPL-3.0-or-later
"""LinkedIn (persönliches Profil) über die Posts API.

Login: Authorization Code über eine eigene LinkedIn-App mit den Produkten
„Share on LinkedIn“ und „Sign In with LinkedIn using OpenID Connect“.
Tokens gelten 60 Tage; danach ist eine neue Anmeldung nötig, die bei
bestehender LinkedIn-Sitzung ohne Rückfrage durchläuft.
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import UTC, datetime, timedelta
from gettext import gettext as _
from typing import Any

from ..auth.oauth import new_state
from ..core import imaging
from ..core.counting import find_hashtags, find_urls, utf16_length
from ..core.models import Media, Profile, ProfileStatus, TargetPart, now_iso
from ..net.http import Request, Response
from ..net.linkcard import fetch_card
from .base import (
    AppLogin,
    AppPlatform,
    Composition,
    Count,
    PlatformError,
    PlatformLimits,
    error_from_status,
)

API = "https://api.linkedin.com"
AUTH = "https://www.linkedin.com/oauth/v2"
#: LinkedIn-Versionen leben etwa ein Jahr; regelmäßig nachziehen
LINKEDIN_VERSION = "202609"
EXPIRING_DAYS = 7
_RESERVED = set("|{}@[]()<>#\\*_~")


def escape_little(text: str) -> str:
    """Escaping für das little-Textformat von `commentary`.

    Alle reservierten Zeichen bekommen einen Backslash. Hashtags werden als
    Hashtag-Element geschrieben, damit sie klickbar bleiben.
    """
    tags = {span.start: span for span in find_hashtags(text)}
    urls = find_urls(text)
    out: list[str] = []
    i = 0
    while i < len(text):
        span = tags.get(i)
        if span is not None and not any(u.start <= i < u.end for u in urls):
            word = "".join("\\" + c if c in _RESERVED else c for c in span.value[1:])
            out.append("{hashtag|\\#|" + word + "}")
            i = span.end
            continue
        ch = text[i]
        out.append("\\" + ch if ch in _RESERVED else ch)
        i += 1
    return "".join(out)


class LinkedIn(AppPlatform):
    id = "linkedin"
    name = "LinkedIn"
    style_class = "platform-linkedin"
    client_secret_mode = "required"
    portal_url = "https://www.linkedin.com/developers/apps"
    scopes = "openid profile w_member_social"

    def default_limits(self) -> PlatformLimits:
        return PlatformLimits(
            max_chars=3000,
            max_images=20,
            max_videos=1,
            allow_mixed_media=False,
            image_mime_types=("image/jpeg", "image/png", "image/gif"),
            video_mime_types=("video/mp4",),
            max_image_bytes=None,       # zu große Bilder werden verkleinert
            max_video_bytes=0,          # Video folgt später
            alt_text_max=4086,
            supports_threads=False,
            client_link_card=True,
            preview_truncate=210,
        )

    def count(self, comp: Composition, limits: PlatformLimits) -> Count:
        return Count(utf16_length(comp.text), limits.max_chars)

    # -- Login -------------------------------------------------------------
    def begin_app_login(self, client_id: str, client_secret: str) -> AppLogin:
        state = new_state()
        q = urllib.parse.urlencode({
            "response_type": "code", "client_id": client_id.strip(),
            "redirect_uri": self.redirect_uri, "state": state, "scope": self.scopes})
        return AppLogin(self.id, f"{AUTH}/authorization?{q}", self.redirect_uri, state,
                        client_id.strip(), client_secret.strip())

    async def complete_app_login(self, login: AppLogin,
                                 code: str) -> list[tuple[Profile, dict[str, Any]]]:
        tok = (await self._send(Request("POST", f"{AUTH}/accessToken", form={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": login.redirect_uri, "client_id": login.client_id,
            "client_secret": login.client_secret}))).json()
        expires_at = time.time() + float(tok.get("expires_in", 60 * 86400))
        info = (await self._send(Request(
            "GET", f"{API}/v2/userinfo",
            headers={"Authorization": f"Bearer {tok['access_token']}"}))).json()
        profile = Profile(platform=self.id, remote_id=str(info["sub"]),
                          handle=info.get("name") or info["sub"],
                          display_name=info.get("name", ""), avatar_url=info.get("picture"),
                          auth_method="byo-oauth",
                          token_expires_at=datetime.fromtimestamp(expires_at, UTC).isoformat(
                              timespec="seconds"))
        secret = {"access_token": tok["access_token"], "expires_at": expires_at,
                  "client_id": login.client_id, "client_secret": login.client_secret}
        return [(profile, secret)]

    # -- Hilfen ------------------------------------------------------------
    def _error(self, resp: Response) -> PlatformError:
        detail = resp.text()[:400]
        try:
            msg = (resp.json() or {}).get("message", "")
        except ValueError:
            msg = ""
        if resp.status == 401:
            return PlatformError(_("The LinkedIn login has expired. Please sign in again."),
                                 detail, auth=True)
        if resp.status == 426 or "version" in msg.lower() and resp.status == 400:
            return PlatformError(_("LinkedIn no longer supports this version of the API. "
                                   "Please update Dandelion."), detail)
        err = error_from_status(resp.status, detail)
        if resp.status in (400, 422) and msg:
            err.message = _("LinkedIn rejected the post: {reason}").format(reason=msg)
        return err

    async def _api(self, profile: Profile, method: str, path: str, **kw: Any) -> Response:
        data = await self._token_data(profile)
        if float(data.get("expires_at", 0)) < time.time():
            raise PlatformError(_("The LinkedIn login has expired. Please sign in again."),
                                auth=True)
        headers = {"Authorization": f"Bearer {data['access_token']}",
                   "Linkedin-Version": LINKEDIN_VERSION,
                   "X-Restli-Protocol-Version": "2.0.0", **kw.pop("headers", {})}
        url = path if path.startswith("http") else f"{API}{path}"
        return await self._send(Request(method, url, headers=headers, **kw))

    @staticmethod
    def _author(profile: Profile) -> str:
        return f"urn:li:person:{profile.remote_id}"

    # -- Netzwerk ----------------------------------------------------------
    async def refresh_profile(self, profile: Profile) -> Profile:
        try:
            data = await self._token_data(profile)
            expires = datetime.fromtimestamp(float(data.get("expires_at", 0)), UTC)
            profile.token_expires_at = expires.isoformat(timespec="seconds")
            info = (await self._api(profile, "GET", "/v2/userinfo")).json()
        except PlatformError as e:
            profile.status = ProfileStatus.EXPIRED if e.auth else ProfileStatus.ERROR
            profile.status_detail = e.message
            return profile
        profile.display_name = info.get("name", profile.display_name)
        profile.avatar_url = info.get("picture", profile.avatar_url)
        left = expires - datetime.now(UTC)
        if left < timedelta(days=EXPIRING_DAYS):
            profile.status = ProfileStatus.EXPIRING
            profile.status_detail = _("The login expires in {days} days.").format(
                days=max(0, left.days))
        else:
            profile.status = ProfileStatus.OK
            profile.status_detail = ""
        profile.limits_json = self.default_limits().to_json()
        profile.limits_fetched_at = now_iso()
        return profile

    async def _upload_image(self, profile: Profile, data: bytes, mime: str) -> str:
        init = (await self._api(profile, "POST", "/rest/images?action=initializeUpload", json={
            "initializeUploadRequest": {"owner": self._author(profile)}})).json()["value"]
        await self._api(profile, "PUT", init["uploadUrl"], data=data, content_type=mime,
                        timeout=300)
        return str(init["image"])

    async def upload_media(self, profile: Profile, media: Media) -> str:
        import json
        if not media.is_image:
            raise PlatformError(_("Videos are not supported for LinkedIn yet."))
        data = imaging.load_bytes(media.path)
        mime = media.mime
        if mime not in ("image/jpeg", "image/png", "image/gif") or \
                (media.width or 0) * (media.height or 0) > 36_000_000:
            data, mime, _w, _h = imaging.shrink_to(data, 8_000_000, max_dim=4000)
        urn = await self._upload_image(profile, data, mime)
        return json.dumps({"id": urn, "altText": media.alt_text.strip()})

    async def post(self, profile: Profile, comp: Composition, media_refs: list[str], *,
                   reply_to: TargetPart | None, root: TargetPart | None,
                   idempotency_key: str) -> TargetPart:
        import json
        body: dict[str, Any] = {
            "author": self._author(profile),
            "commentary": escape_little(comp.text),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        images = [json.loads(r) for r in media_refs]
        for img in images:
            if not img.get("altText"):
                img.pop("altText", None)
        if len(images) == 1:
            body["content"] = {"media": images[0]}
        elif images:
            body["content"] = {"multiImage": {"images": images}}
        else:
            urls = find_urls(comp.text)
            if urls:
                article = await self._article(profile, urls[0].value)
                if article:
                    body["content"] = {"article": article}
        resp = await self._api(profile, "POST", "/rest/posts", json=body)
        urn = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id", "")
        url = f"https://www.linkedin.com/feed/update/{urn}/" if urn else None
        return TargetPart(idx=0, remote_id=urn, remote_url=url)

    async def _article(self, profile: Profile, url: str) -> dict[str, Any] | None:
        card = await fetch_card(self.http, url)
        if not card or not card.title:
            return None
        article: dict[str, Any] = {"source": url, "title": card.title[:200]}
        if card.description:
            article["description"] = card.description[:300]
        if card.image_data:
            try:
                data, mime = card.image_data, card.image_mime or "image/jpeg"
                if mime not in ("image/jpeg", "image/png", "image/gif"):
                    data, mime, _w, _h = imaging.shrink_to(data, 5_000_000)
                article["thumbnail"] = await self._upload_image(profile, data, mime)
            except (ValueError, PlatformError):
                pass
        return article

    async def delete(self, profile: Profile, part: TargetPart) -> None:
        if part.remote_id:
            urn = urllib.parse.quote(part.remote_id, safe="")
            await self._api(profile, "DELETE", f"/rest/posts/{urn}")
