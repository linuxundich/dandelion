# SPDX-License-Identifier: GPL-3.0-or-later
"""Mastodon lesen: Home-Timeline über die REST-Schnittstelle."""

from __future__ import annotations

from ..core.models import Profile
from ..platforms.base import PlatformError
from ..platforms.mastodon import Mastodon
from .base import (
    FeedAccount,
    FeedCard,
    FeedMedia,
    FeedPost,
    ReadScopeMissing,
    Reader,
)


def _account(data: dict) -> FeedAccount:
    return FeedAccount(
        id=str(data.get("id", "")), acct=data.get("acct") or data.get("username", ""),
        display_name=data.get("display_name") or "",
        avatar_url=data.get("avatar_static") or data.get("avatar"), url=data.get("url") or "")


def _media(data: dict) -> FeedMedia:
    kind = data.get("type", "other")
    if kind not in ("image", "video", "gifv", "audio"):
        kind = "other"
    return FeedMedia(kind, data.get("url") or data.get("remote_url") or "",
                     data.get("preview_url"), data.get("description") or "")


def parse_status(raw: dict) -> FeedPost:
    """Ein Mastodon-Status; bei einem Boost zählt der Inhalt des Originals."""
    boosted_by = None
    status = raw
    if raw.get("reblog"):
        boosted_by = _account(raw["account"])
        status = raw["reblog"]
    card = None
    c = status.get("card")
    if c and c.get("url"):
        card = FeedCard(c["url"], c.get("title") or c["url"], c.get("description") or "",
                        c.get("image"))
    return FeedPost(
        id=str(raw["id"]), network="mastodon", account=_account(status["account"]),
        created_at=status.get("created_at") or raw.get("created_at") or "",
        html=status.get("content") or "", spoiler=status.get("spoiler_text") or "",
        sensitive=bool(status.get("sensitive")), url=status.get("url") or status.get("uri") or "",
        language=status.get("language"),
        media=[_media(m) for m in status.get("media_attachments", [])], card=card,
        boosted_by=boosted_by, replies=int(status.get("replies_count") or 0),
        boosts=int(status.get("reblogs_count") or 0),
        likes=int(status.get("favourites_count") or 0), has_poll=bool(status.get("poll")))


class MastodonReader(Reader):
    network = "mastodon"

    def __init__(self, platform: Mastodon) -> None:
        self.platform = platform

    def parse(self, raw: dict) -> FeedPost:
        return parse_status(raw)

    async def fetch_home(self, profile: Profile, *, before: str | None = None,
                         limit: int = 40) -> tuple[list[dict], list[FeedPost]]:
        params: dict[str, object] = {"limit": limit}
        if before:
            params["max_id"] = before
        try:
            resp = await self.platform._api(profile, "GET", "/api/v1/timelines/home", params=params)
        except PlatformError as e:
            if e.auth and "scope" in e.detail.lower():
                raise ReadScopeMissing(
                    e.message, e.detail, auth=True) from e
            raise
        raw = resp.json() or []
        return raw, [parse_status(r) for r in raw]
