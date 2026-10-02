# SPDX-License-Identifier: GPL-3.0-or-later
"""Mastodon (und kompatible Server).

Login: App wird pro Instanz und Login dynamisch registriert
(`POST /api/v1/apps`), dann Authorization Code mit PKCE über den
Systembrowser. Redirect auf einen Loopback-Port, Ersatzweise `oob` mit
manueller Code-Eingabe.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.parse
from dataclasses import dataclass
from gettext import gettext as _
from typing import Any

from ..auth.oauth import Pkce, new_state
from ..core.counting import mastodon_count
from ..core.models import Media, Profile, ProfileStatus, TargetPart, now_iso
from ..net.http import FilePart, NetworkError, Request, Response
from .base import (
    Composition,
    Count,
    Platform,
    PlatformError,
    PlatformLimits,
    error_from_status,
    json_or_text,
    secret_label,
)

SCOPES = "read:accounts write:statuses write:media"
OOB = "urn:ietf:wg:oauth:2.0:oob"
APP_NAME = "Dandelion"
APP_WEBSITE = "https://github.com/linuxundich/dandelion"


def normalize_instance(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"^https?://", "", text)
    text = text.split("/")[0]
    if "@" in text:           # „@user@instanz“ oder „user@instanz“
        text = text.rsplit("@", 1)[1]
    return text


@dataclass
class PendingLogin:
    instance: str
    client_id: str
    client_secret: str
    redirect_uri: str
    pkce: Pkce
    state: str

    def authorize_url(self) -> str:
        q = urllib.parse.urlencode({
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": SCOPES,
            "state": self.state,
            "code_challenge": self.pkce.challenge,
            "code_challenge_method": self.pkce.method,
            "force_login": "true",
        })
        return f"https://{self.instance}/oauth/authorize?{q}"


class Mastodon(Platform):
    id = "mastodon"
    name = "Mastodon"
    style_class = "platform-mastodon"

    def default_limits(self) -> PlatformLimits:
        return PlatformLimits(
            max_chars=500,
            url_weight=23,
            max_images=4,
            max_videos=1,
            allow_mixed_media=False,
            image_mime_types=("image/jpeg", "image/png", "image/gif", "image/webp",
                              "image/heic", "image/heif", "image/avif"),
            video_mime_types=("video/mp4", "video/webm", "video/quicktime"),
            max_image_bytes=16 * 1024 * 1024,
            max_video_bytes=99 * 1024 * 1024,
            alt_text_max=1500,
            alt_text_required=True,
            supports_content_warning=True,
            visibility_options=("public", "unlisted", "private", "direct"),
            max_languages=1,
            supports_threads=True,
            client_link_card=False,
        )

    def count(self, comp: Composition, limits: PlatformLimits) -> Count:
        used = mastodon_count(comp.text, comp.content_warning, limits.url_weight or 23)
        return Count(used, limits.max_chars)

    # -- Login -------------------------------------------------------------
    async def begin_login(self, instance: str, redirect_uri: str) -> PendingLogin:
        instance = normalize_instance(instance)
        if not instance or "." not in instance:
            raise PlatformError(_("Please enter the address of your Mastodon server, "
                                  "for example mastodon.social."))
        resp = await self._send(Request(
            "POST", f"https://{instance}/api/v1/apps",
            form={"client_name": APP_NAME, "redirect_uris": f"{redirect_uri}\n{OOB}",
                  "scopes": SCOPES, "website": APP_WEBSITE}),
            not_found=_("No Mastodon server was found at {instance}.").format(instance=instance))
        data = resp.json()
        return PendingLogin(instance, data["client_id"], data["client_secret"], redirect_uri,
                            Pkce.create(), new_state())

    async def finish_login(self, pending: PendingLogin, code: str,
                           redirect_uri: str) -> tuple[Profile, dict[str, Any]]:
        resp = await self._send(Request(
            "POST", f"https://{pending.instance}/oauth/token",
            form={"grant_type": "authorization_code", "code": code,
                  "client_id": pending.client_id, "client_secret": pending.client_secret,
                  "redirect_uri": redirect_uri, "code_verifier": pending.pkce.verifier,
                  "scope": SCOPES}))
        token = resp.json()["access_token"]
        account = (await self._send(Request(
            "GET", f"https://{pending.instance}/api/v1/accounts/verify_credentials",
            headers={"Authorization": f"Bearer {token}"}))).json()
        profile = Profile(
            platform=self.id, server=pending.instance, remote_id=str(account["id"]),
            handle=account["username"], display_name=account.get("display_name") or "",
            avatar_url=account.get("avatar_static") or account.get("avatar"),
            auth_method="oauth",
        )
        secret = {"access_token": token, "client_id": pending.client_id,
                  "client_secret": pending.client_secret}
        return profile, secret

    async def store_credentials(self, profile: Profile, secret: dict[str, Any]) -> None:
        await self.secrets.set(profile.uuid, "oauth", secret_label(self, profile), secret)

    # -- Hilfen ------------------------------------------------------------
    async def _token(self, profile: Profile) -> str:
        data = await self.secrets.get(profile.uuid, "oauth")
        if not data or not data.get("access_token"):
            raise PlatformError(_("No login data found. Please sign in again."), auth=True)
        return str(data["access_token"])

    async def _send(self, req: Request, *, not_found: str | None = None) -> Response:
        try:
            resp = await self.http.send(req)
        except NetworkError as e:
            raise PlatformError(_("The server could not be reached. Check your internet "
                                  "connection."), str(e), retryable=True) from e
        if resp.ok:
            return resp
        detail = ""
        try:
            body = resp.json()
            detail = body.get("error", "") if isinstance(body, dict) else json_or_text(body)
        except ValueError:
            detail = resp.text()[:300]
        if resp.status == 404 and not_found:
            raise PlatformError(not_found, detail)
        err = error_from_status(resp.status, detail)
        if resp.status == 422 and detail:
            err.message = _("The server rejected the post: {reason}").format(reason=detail)
        raise err

    async def _api(self, profile: Profile, method: str, path: str, **kw: Any) -> Response:
        token = await self._token(profile)
        headers = {"Authorization": f"Bearer {token}", **kw.pop("headers", {})}
        return await self._send(Request(method, f"https://{profile.server}{path}",
                                        headers=headers, **kw))

    # -- Netzwerk ----------------------------------------------------------
    async def fetch_limits(self, profile: Profile) -> PlatformLimits:
        limits = self.default_limits()
        try:
            resp = await self._send(Request("GET", f"https://{profile.server}/api/v2/instance"))
        except PlatformError:
            return limits
        conf = (resp.json() or {}).get("configuration", {})
        st = conf.get("statuses", {})
        ma = conf.get("media_attachments", {})
        limits.max_chars = int(st.get("max_characters", limits.max_chars))
        limits.url_weight = int(st.get("characters_reserved_per_url", limits.url_weight or 23))
        limits.max_images = int(st.get("max_media_attachments", limits.max_images))
        if ma.get("supported_mime_types"):
            types = ma["supported_mime_types"]
            limits.image_mime_types = tuple(t for t in types if t.startswith("image/"))
            limits.video_mime_types = tuple(t for t in types if t.startswith("video/"))
        if ma.get("image_size_limit"):
            limits.max_image_bytes = int(ma["image_size_limit"])
        if ma.get("video_size_limit"):
            limits.max_video_bytes = int(ma["video_size_limit"])
        if ma.get("description_limit"):
            limits.alt_text_max = int(ma["description_limit"])
        return limits

    async def refresh_profile(self, profile: Profile) -> Profile:
        try:
            account = (await self._api(profile, "GET", "/api/v1/accounts/verify_credentials")).json()
        except PlatformError as e:
            profile.status = ProfileStatus.EXPIRED if e.auth else ProfileStatus.ERROR
            profile.status_detail = e.message
            return profile
        profile.handle = account["username"]
        profile.display_name = account.get("display_name") or ""
        profile.avatar_url = account.get("avatar_static") or account.get("avatar")
        profile.status = ProfileStatus.OK
        profile.status_detail = ""
        limits = await self.fetch_limits(profile)
        profile.limits_json = limits.to_json()
        profile.limits_fetched_at = now_iso()
        return profile

    async def upload_media(self, profile: Profile, media: Media) -> str:
        with open(media.path, "rb") as fh:
            data = fh.read()
        resp = await self._api(
            profile, "POST", "/api/v2/media",
            form={"description": media.alt_text or None,
                  **({"focus": f"{media.focus_x},{media.focus_y}"}
                     if media.focus_x is not None else {})},
            files=[FilePart("file", os.path.basename(media.path), media.mime, data)],
            timeout=300)
        att = resp.json()
        media_id = str(att["id"])
        # Video/GIFV wird asynchron verarbeitet (202), dann abfragen
        delay = 1.0
        for _i in range(60):
            if resp.status != 202 and att.get("url"):
                break
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 5.0)
            resp = await self._api(profile, "GET", f"/api/v1/media/{media_id}")
            att = resp.json()
            if resp.status == 200 and att.get("url"):
                break
        return json.dumps({"id": media_id})

    async def post(self, profile: Profile, comp: Composition, media_refs: list[str], *,
                   reply_to: TargetPart | None, root: TargetPart | None,
                   idempotency_key: str) -> TargetPart:
        form = {**self._status_form(comp, media_refs),
                "in_reply_to_id": reply_to.remote_id if reply_to else None}
        resp = await self._api(profile, "POST", "/api/v1/statuses", form=form,
                               headers={"Idempotency-Key": idempotency_key})
        st = resp.json()
        return TargetPart(idx=0, remote_id=str(st["id"]), remote_url=st.get("url") or st.get("uri"))

    # -- Serverseitiges Planen ---------------------------------------------
    def _status_form(self, comp: Composition, media_refs: list[str]) -> dict[str, Any]:
        return {
            "status": comp.text,
            "media_ids[]": [json.loads(r)["id"] for r in media_refs] or None,
            "spoiler_text": comp.content_warning or None,
            "sensitive": True if comp.content_warning else None,
            "visibility": comp.visibility or None,
            "language": comp.language or None,
        }

    async def schedule_remote(self, profile: Profile, comp: Composition, media_refs: list[str],
                              at: str, idempotency_key: str) -> str:
        """Legt einen geplanten Beitrag auf dem Server an und liefert dessen ID."""
        form = {**self._status_form(comp, media_refs), "scheduled_at": at}
        resp = await self._api(profile, "POST", "/api/v1/statuses", form=form,
                               headers={"Idempotency-Key": idempotency_key})
        data = resp.json() or {}
        if "scheduled_at" not in data:
            raise PlatformError(_("The server published the post immediately instead of "
                                  "scheduling it."), json_or_text(data))
        return str(data["id"])

    async def cancel_remote(self, profile: Profile, scheduled_id: str) -> None:
        try:
            await self._api(profile, "DELETE", f"/api/v1/scheduled_statuses/{scheduled_id}")
        except PlatformError as e:
            if "404" not in e.detail and "not found" not in e.message.lower():
                raise

    async def find_published(self, profile: Profile, at: str) -> TargetPart | None:
        """Sucht den vom Server veröffentlichten Beitrag zum geplanten Zeitpunkt."""
        from datetime import datetime
        planned = datetime.fromisoformat(at)
        resp = await self._api(profile, "GET", f"/api/v1/accounts/{profile.remote_id}/statuses",
                               params={"limit": 20, "exclude_reblogs": True})
        best: tuple[float, dict[str, Any]] | None = None
        for st in resp.json() or []:
            created = datetime.fromisoformat(str(st["created_at"]).replace("Z", "+00:00"))
            diff = abs((created - planned).total_seconds())
            if diff <= 15 * 60 and (best is None or diff < best[0]):
                best = (diff, st)
        if best is None:
            return None
        st = best[1]
        return TargetPart(idx=0, remote_id=str(st["id"]), remote_url=st.get("url") or st.get("uri"))

    async def delete(self, profile: Profile, part: TargetPart) -> None:
        if part.remote_id:
            await self._api(profile, "DELETE", f"/api/v1/statuses/{part.remote_id}")

    async def logout(self, profile: Profile) -> None:
        data = await self.secrets.get(profile.uuid, "oauth")
        if data and profile.server:
            try:
                await self._send(Request("POST", f"https://{profile.server}/oauth/revoke", form={
                    "client_id": data.get("client_id"), "client_secret": data.get("client_secret"),
                    "token": data.get("access_token")}))
            except PlatformError:
                pass
        await super().logout(profile)
