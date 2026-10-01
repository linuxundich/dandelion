# SPDX-License-Identifier: GPL-3.0-or-later
"""Bluesky über das AT Protocol.

Standard-Login ist ein App-Passwort: Damit kann Dandelion die Sitzung
jederzeit neu aufbauen, auch für Wochen im Voraus geplante Beiträge.
(OAuth als Option folgt später.)
"""

from __future__ import annotations

import base64
import json
import re
import time
from datetime import UTC, datetime
from gettext import gettext as _
from typing import Any

from ..core import imaging
from ..core.counting import (
    bluesky_count,
    bluesky_display_text,
    bluesky_shorten_url,
    find_hashtags,
    find_urls,
)
from ..core.models import Media, Profile, ProfileStatus, TargetPart
from ..net.http import NetworkError, Request, Response
from ..net.linkcard import fetch_card
from .base import (
    Composition,
    Count,
    Platform,
    PlatformError,
    PlatformLimits,
    error_from_status,
    secret_label,
)

APPVIEW = "https://public.api.bsky.app"
PLC = "https://plc.directory"
IMAGE_MAX = 2_000_000
THUMB_MAX = 1_000_000
CONTENT_LABELS = ("sexual", "nudity", "porn", "graphic-media")

# Bluesky-Mentions: @handle.mit.punkt, aber nicht @user@instanz (Fediverse)
BSKY_MENTION_RE = re.compile(r"(?<![\w@/])@([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?"
                             r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)+)(?![\w@])")


def normalize_handle(text: str) -> str:
    text = text.strip().lstrip("@").lower()
    if text and "." not in text and not text.startswith("did:"):
        text += ".bsky.social"
    return text


def _jwt_exp(token: str) -> float:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, KeyError, ValueError):
        return 0.0


def _byte_offset(text: str, index: int) -> int:
    return len(text[:index].encode("utf-8"))


def post_url(handle: str, uri: str) -> str:
    rkey = uri.rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{handle}/post/{rkey}"


class Bluesky(Platform):
    id = "bluesky"
    name = "Bluesky"
    style_class = "platform-bluesky"

    def default_limits(self) -> PlatformLimits:
        return PlatformLimits(
            max_chars=300,
            max_bytes=3000,
            url_weight=None,
            max_images=4,
            max_videos=1,
            allow_mixed_media=False,
            image_mime_types=("image/jpeg", "image/png", "image/webp", "image/gif",
                              "image/heic", "image/avif"),
            video_mime_types=("video/mp4",),
            max_image_bytes=None,          # größere Bilder werden verkleinert
            max_video_bytes=0,             # Video folgt in einer späteren Version
            alt_text_max=2000,
            alt_text_required=False,
            supports_content_warning=False,
            content_labels=CONTENT_LABELS,
            max_languages=3,
            supports_threads=True,
            client_link_card=True,
        )

    def count(self, comp: Composition, limits: PlatformLimits) -> Count:
        graphemes, nbytes = bluesky_count(comp.text)
        return Count(graphemes, limits.max_chars, nbytes, limits.max_bytes)

    def display_text(self, text: str) -> str:
        return bluesky_display_text(text)

    # -- Sitzung -----------------------------------------------------------
    async def _send(self, req: Request) -> Response:
        try:
            resp = await self.http.send(req)
        except NetworkError as e:
            raise PlatformError(_("Bluesky could not be reached. Check your internet "
                                  "connection."), str(e), retryable=True) from e
        if resp.ok:
            return resp
        err, msg = "", ""
        try:
            body = resp.json() or {}
            err, msg = body.get("error", ""), body.get("message", "")
        except ValueError:
            msg = resp.text()[:300]
        if err in ("AuthenticationRequired", "InvalidToken") or resp.status == 401:
            raise PlatformError(_("Bluesky did not accept the login. Check the handle and "
                                  "the app password."), f"{err}: {msg}", auth=True)
        if err == "ExpiredToken":
            raise PlatformError("expired", err, auth=True, retryable=True)
        if err == "AccountTakedown":
            raise PlatformError(_("This Bluesky account has been suspended."), err)
        if err == "RateLimitExceeded":
            raise PlatformError(_("Too many requests. Please try again later."), err,
                                retryable=True)
        if err == "BlobTooLarge":
            raise PlatformError(_("A file is too large for Bluesky."), msg)
        e = error_from_status(resp.status, f"{err}: {msg}")
        if resp.status == 400 and msg:
            e.message = _("Bluesky rejected the post: {reason}").format(reason=msg)
        raise e

    async def resolve_pds(self, handle_or_did: str) -> tuple[str, str]:
        """Liefert (DID, PDS-URL) für ein Handle oder eine DID."""
        did = handle_or_did
        if not did.startswith("did:"):
            try:
                resp = await self._send(Request(
                    "GET", f"{APPVIEW}/xrpc/com.atproto.identity.resolveHandle",
                    params={"handle": handle_or_did}))
            except PlatformError as e:
                raise PlatformError(_("The handle {handle} was not found on Bluesky.").format(
                    handle=handle_or_did), e.detail) from e
            did = resp.json()["did"]
        if did.startswith("did:plc:"):
            doc = (await self._send(Request("GET", f"{PLC}/{did}"))).json()
        elif did.startswith("did:web:"):
            host = did.removeprefix("did:web:")
            doc = (await self._send(Request("GET", f"https://{host}/.well-known/did.json"))).json()
        else:
            raise PlatformError(_("Unsupported identity: {did}").format(did=did))
        for svc in doc.get("service", []):
            if svc.get("id", "").endswith("#atproto_pds"):
                return did, str(svc["serviceEndpoint"]).rstrip("/")
        raise PlatformError(_("No Bluesky server (PDS) was found for this account."))

    async def login_app_password(self, handle: str,
                                 app_password: str) -> tuple[Profile, dict[str, Any]]:
        handle = normalize_handle(handle)
        did, pds = await self.resolve_pds(handle)
        resp = await self._send(Request(
            "POST", f"{pds}/xrpc/com.atproto.server.createSession",
            json={"identifier": did, "password": app_password.strip()}))
        sess = resp.json()
        secret = {"pds": pds, "did": did, "app_password": app_password.strip(),
                  "access_jwt": sess["accessJwt"], "refresh_jwt": sess["refreshJwt"]}
        profile = Profile(platform=self.id, server=pds, remote_id=did,
                          handle=sess.get("handle", handle), auth_method="app-password")
        await self._fill_profile(profile, pds, sess["accessJwt"])
        return profile, secret

    async def store_credentials(self, profile: Profile, secret: dict[str, Any]) -> None:
        await self.secrets.set(profile.uuid, "app-password", secret_label(self, profile), secret)

    async def _session(self, profile: Profile, force_refresh: bool = False) -> dict[str, Any]:
        data = await self.secrets.get(profile.uuid, "app-password")
        if not data:
            raise PlatformError(_("No login data found. Please sign in again."), auth=True)
        if not force_refresh and _jwt_exp(data.get("access_jwt", "")) > time.time() + 60:
            return data
        pds = data["pds"]
        try:
            resp = await self._send(Request(
                "POST", f"{pds}/xrpc/com.atproto.server.refreshSession",
                headers={"Authorization": f"Bearer {data['refresh_jwt']}"}))
        except PlatformError as e:
            if not e.auth:
                raise
            # Refresh abgelaufen: mit dem App-Passwort neu anmelden
            resp = await self._send(Request(
                "POST", f"{pds}/xrpc/com.atproto.server.createSession",
                json={"identifier": data["did"], "password": data["app_password"]}))
        sess = resp.json()
        data["access_jwt"], data["refresh_jwt"] = sess["accessJwt"], sess["refreshJwt"]
        await self.secrets.set(profile.uuid, "app-password", secret_label(self, profile), data)
        return data

    async def _xrpc(self, profile: Profile, method: str, nsid: str, **kw: Any) -> Response:
        sess = await self._session(profile)
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {sess['access_jwt']}", **kw.get("headers", {})}
            req = Request(method, f"{sess['pds']}/xrpc/{nsid}",
                          **{**kw, "headers": headers})
            try:
                return await self._send(req)
            except PlatformError as e:
                if e.message == "expired" and attempt == 1:
                    sess = await self._session(profile, force_refresh=True)
                    continue
                raise
        raise AssertionError("unreachable")

    async def _fill_profile(self, profile: Profile, pds: str, token: str) -> None:
        resp = await self._send(Request(
            "GET", f"{pds}/xrpc/app.bsky.actor.getProfile", params={"actor": profile.remote_id},
            headers={"Authorization": f"Bearer {token}"}))
        p = resp.json()
        profile.handle = p.get("handle", profile.handle)
        profile.display_name = p.get("displayName") or ""
        profile.avatar_url = p.get("avatar")

    # -- Netzwerk ----------------------------------------------------------
    async def refresh_profile(self, profile: Profile) -> Profile:
        try:
            sess = await self._session(profile)
            await self._fill_profile(profile, sess["pds"], sess["access_jwt"])
        except PlatformError as e:
            profile.status = ProfileStatus.EXPIRED if e.auth else ProfileStatus.ERROR
            profile.status_detail = e.message
            return profile
        profile.status = ProfileStatus.OK
        profile.status_detail = ""
        profile.limits_json = self.default_limits().to_json()
        return profile

    async def _upload_blob(self, profile: Profile, data: bytes, mime: str) -> dict[str, Any]:
        resp = await self._xrpc(profile, "POST", "com.atproto.repo.uploadBlob", data=data,
                                content_type=mime, timeout=300)
        return dict(resp.json()["blob"])

    async def upload_media(self, profile: Profile, media: Media) -> str:
        if not media.is_image:
            raise PlatformError(_("Videos are not supported for Bluesky yet."))
        data = imaging.load_bytes(media.path)
        mime, w, h = media.mime, media.width, media.height
        if len(data) > IMAGE_MAX or mime not in ("image/jpeg", "image/png", "image/webp"):
            data, mime, w, h = imaging.shrink_to(data, IMAGE_MAX)
        blob = await self._upload_blob(profile, data, mime)
        ref: dict[str, Any] = {"image": blob, "alt": media.alt_text or ""}
        if w and h:
            ref["aspectRatio"] = {"width": w, "height": h}
        return json.dumps(ref)

    async def build_facets(self, text: str,
                           links: list[tuple[int, int, str]]) -> list[dict[str, Any]]:
        """Facets für den bereits gekürzten Text; Links zeigen auf die volle URL."""
        facets: list[dict[str, Any]] = []
        # Links: im gespeicherten Text stehen Kurzformen, `links` kennt die Ziel-URLs
        for start, end, uri in links:
            facets.append({"index": {"byteStart": _byte_offset(text, start),
                                     "byteEnd": _byte_offset(text, end)},
                           "features": [{"$type": "app.bsky.richtext.facet#link", "uri": uri}]})
        for m in BSKY_MENTION_RE.finditer(text):
            handle = m.group(1).lower()
            if any(s <= m.start() < e for s, e, _u in links):
                continue
            try:
                resp = await self._send(Request(
                    "GET", f"{APPVIEW}/xrpc/com.atproto.identity.resolveHandle",
                    params={"handle": handle}))
            except PlatformError:
                continue
            facets.append({"index": {"byteStart": _byte_offset(text, m.start()),
                                     "byteEnd": _byte_offset(text, m.end())},
                           "features": [{"$type": "app.bsky.richtext.facet#mention",
                                         "did": resp.json()["did"]}]})
        for span in find_hashtags(text):
            tag = span.value[1:]
            if len(tag) > 64:
                continue
            facets.append({"index": {"byteStart": _byte_offset(text, span.start),
                                     "byteEnd": _byte_offset(text, span.end)},
                           "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}]})
        facets.sort(key=lambda f: f["index"]["byteStart"])
        return facets

    def shorten(self, text: str) -> tuple[str, list[tuple[int, int, str]]]:
        """Kürzt URLs und liefert (Text, [(start, end, volle URL)])."""
        out, spans, last, pos = [], [], 0, 0
        for span in find_urls(text):
            out.append(text[last:span.start])
            pos += span.start - last
            short = bluesky_shorten_url(span.value)
            spans.append((pos, pos + len(short), span.value))
            out.append(short)
            pos += len(short)
            last = span.end
        out.append(text[last:])
        return "".join(out), spans

    async def post(self, profile: Profile, comp: Composition, media_refs: list[str], *,
                   reply_to: TargetPart | None, root: TargetPart | None,
                   idempotency_key: str) -> TargetPart:
        sess = await self._session(profile)
        text, spans = self.shorten(comp.text)
        facets = await self.build_facets(text, spans)
        record: dict[str, Any] = {
            "$type": "app.bsky.feed.post",
            "text": text,
            "createdAt": datetime.now(UTC).isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"),
        }
        if facets:
            record["facets"] = facets
        if comp.language:
            record["langs"] = [comp.language]
        if media_refs:
            record["embed"] = {"$type": "app.bsky.embed.images",
                               "images": [json.loads(r) for r in media_refs]}
        elif spans:
            embed = await self._link_embed(profile, spans[0][2])
            if embed:
                record["embed"] = embed
        if comp.content_label in CONTENT_LABELS:
            record["labels"] = {"$type": "com.atproto.label.defs#selfLabels",
                                "values": [{"val": comp.content_label}]}
        if reply_to and reply_to.remote_id and reply_to.remote_cid:
            r = root or reply_to
            record["reply"] = {"root": {"uri": r.remote_id, "cid": r.remote_cid},
                               "parent": {"uri": reply_to.remote_id, "cid": reply_to.remote_cid}}
        resp = await self._xrpc(profile, "POST", "com.atproto.repo.createRecord", json={
            "repo": sess["did"], "collection": "app.bsky.feed.post", "record": record})
        data = resp.json()
        return TargetPart(idx=0, remote_id=data["uri"], remote_cid=data["cid"],
                          remote_url=post_url(profile.handle, data["uri"]))

    async def _link_embed(self, profile: Profile, url: str) -> dict[str, Any] | None:
        card = await fetch_card(self.http, url)
        if not card or not (card.title or card.description):
            return None
        external: dict[str, Any] = {"uri": url, "title": card.title,
                                    "description": card.description}
        if card.image_data:
            try:
                data, mime = card.image_data, card.image_mime or "image/jpeg"
                if len(data) > THUMB_MAX or mime not in ("image/jpeg", "image/png", "image/webp"):
                    data, mime, _w, _h = imaging.shrink_to(data, THUMB_MAX, max_dim=1200)
                external["thumb"] = await self._upload_blob(profile, data, mime)
            except (ValueError, PlatformError):
                pass
        return {"$type": "app.bsky.embed.external", "external": external}

    async def delete(self, profile: Profile, part: TargetPart) -> None:
        if not part.remote_id:
            return
        sess = await self._session(profile)
        await self._xrpc(profile, "POST", "com.atproto.repo.deleteRecord", json={
            "repo": sess["did"], "collection": "app.bsky.feed.post",
            "rkey": part.remote_id.rsplit("/", 1)[-1]})

    async def logout(self, profile: Profile) -> None:
        try:
            data = await self.secrets.get(profile.uuid, "app-password")
            if data:
                await self._send(Request(
                    "POST", f"{data['pds']}/xrpc/com.atproto.server.deleteSession",
                    headers={"Authorization": f"Bearer {data['refresh_jwt']}"}))
        except PlatformError:
            pass
        await super().logout(profile)
