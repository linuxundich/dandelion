# SPDX-License-Identifier: GPL-3.0-or-later
"""Mastodon lesen: Home-Timeline, Benachrichtigungen und Konversationen."""

from __future__ import annotations

import re
import urllib.parse
from gettext import gettext as _


from ..core.models import Profile
from ..platforms.base import PlatformError
from ..platforms.mastodon import Mastodon
from .base import (
    HOME,
    MESSAGES,
    NOTIFICATIONS,
    ACTIONS,
    RELATIONS,
    FeedAccount,
    FeedCard,
    FeedConversation,
    FeedItem,
    FeedMedia,
    FeedPoll,
    FeedSource,
    FeedPost,
    Page,
    ReadScopeMissing,
    Reader,
    Relationship,
    norm_ts,
)

#: Mastodon-Typ → Anlass im gemeinsamen Format
REASONS = {"mention": "mention", "status": "status", "reblog": "boost", "follow": "follow",
           "follow_request": "follow_request", "favourite": "favourite", "poll": "poll",
           "update": "update", "quote": "quote"}
NOTIFICATION_TYPES = list(REASONS)
PATHS = {HOME: "/api/v1/timelines/home", NOTIFICATIONS: "/api/v1/notifications",
         MESSAGES: "/api/v1/conversations", "bookmarks": "/api/v1/bookmarks",
         "favourites": "/api/v1/favourites"}
LINK_NEXT = re.compile(r'<[^>]*[?&]max_id=([^&>]+)[^>]*>;\s*rel="next"')


def path_for(feed: str) -> str:
    """REST-Pfad einer Liste; `list:ID` und `tag:NAME` sind eigene Spalten."""
    if feed in PATHS:
        return PATHS[feed]
    kind, _, key = feed.partition(":")
    if kind == "list" and key:
        return f"/api/v1/timelines/list/{urllib.parse.quote(key, safe='')}"
    if kind == "tag" and key:
        return f"/api/v1/timelines/tag/{urllib.parse.quote(key, safe='')}"
    raise ValueError(feed)


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


def _poll(data: dict) -> FeedPoll:
    return FeedPoll([(o.get("title", ""), int(o.get("votes_count") or 0))
                     for o in data.get("options", [])],
                    int(data.get("votes_count") or 0), bool(data.get("expired")),
                    bool(data.get("multiple")))


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
    post = FeedPost(
        id=str(raw["id"]), network="mastodon", account=_account(status["account"]),
        created_at=status.get("created_at") or raw.get("created_at") or "",
        html=status.get("content") or "", spoiler=status.get("spoiler_text") or "",
        sensitive=bool(status.get("sensitive")), url=status.get("url") or status.get("uri") or "",
        language=status.get("language"),
        media=[_media(m) for m in status.get("media_attachments", [])], card=card,
        poll=_poll(status["poll"]) if status.get("poll") else None,
        boosted_by=boosted_by, replies=int(status.get("replies_count") or 0),
        boosts=int(status.get("reblogs_count") or 0),
        likes=int(status.get("favourites_count") or 0),
        ref=str(status["id"]), visibility=status.get("visibility"),
        favourited=bool(status.get("favourited")), boosted=bool(status.get("reblogged")),
        bookmarked=bool(status.get("bookmarked")),
        is_reply=bool(status.get("in_reply_to_id")) and
        str(status.get("in_reply_to_account_id") or "") != str(status["account"].get("id", "")))
    _apply_filters(post, status.get("filtered") or [])
    return post


def _apply_filters(post: FeedPost, matches: list[dict]) -> None:
    """Filter des Servers (Einstellungen > Filter): ausblenden oder hinter Warnung zuklappen."""
    for match in matches:
        flt = match.get("filter") or {}
        if flt.get("filter_action") == "hide":
            post.hidden = True
        elif flt.get("title") and not post.filter_title:
            post.filter_title = flt["title"]
    if post.filter_title and not post.spoiler:
        post.spoiler = _("Filtered: {title}").format(title=post.filter_title)
        post.sensitive = True


def parse_notification(raw: dict) -> FeedPost:
    reason = REASONS.get(raw.get("type", ""), "other")
    actor = _account(raw["account"])
    status = parse_status(raw["status"]) if raw.get("status") else None
    if status is not None and reason in ("mention", "status", "update", "quote"):
        status.id = str(raw["id"])
        status.reason = reason
        return status
    return FeedPost(id=str(raw["id"]), network="mastodon", account=actor,
                    created_at=raw.get("created_at") or "", reason=reason, subject=status)


def parse_conversation(raw: dict) -> FeedConversation:
    last = parse_status(raw["last_status"]) if raw.get("last_status") else None
    return FeedConversation(
        id=str(raw["id"]), created_at=last.created_at if last else "",
        accounts=[_account(a) for a in raw.get("accounts", [])], last=last,
        unread=bool(raw.get("unread")))


class MastodonReader(Reader):
    network = "mastodon"
    feeds = (HOME, NOTIFICATIONS, MESSAGES)

    def __init__(self, platform: Mastodon) -> None:
        self.platform = platform

    def parse(self, feed: str, raw: dict) -> FeedItem:
        if feed == NOTIFICATIONS:
            return parse_notification(raw)
        if feed == MESSAGES:
            return parse_conversation(raw)
        return parse_status(raw)

    def key(self, feed: str, raw: dict) -> tuple[str, str]:
        if feed == MESSAGES:
            last = raw.get("last_status") or {}
            return str(raw["id"]), norm_ts(last.get("created_at") or "")
        return str(raw["id"]), norm_ts(raw.get("created_at") or "")

    async def _response(self, profile: Profile, path: str, params: dict):  # type: ignore[no-untyped-def]
        try:
            return await self.platform._api(profile, "GET", path, params=params)
        except PlatformError as e:
            if e.auth and "scope" in e.detail.lower():
                raise ReadScopeMissing(e.message, e.detail, auth=True) from e
            raise

    async def _get(self, profile: Profile, path: str, params: dict) -> list | dict:
        return (await self._response(profile, path, params)).json() or []

    def cursor_in_cache(self, feed: str) -> bool:
        # Lesezeichen und Favoriten blättern mit eigenen IDs aus dem Link-Header
        return feed not in ("bookmarks", "favourites")

    async def fetch(self, profile: Profile, feed: str, *, cursor: str | None = None,
                    limit: int = 40) -> Page:
        params: dict[str, object] = {"limit": limit}
        if cursor:
            params["max_id"] = cursor
        if feed == NOTIFICATIONS:
            params["types[]"] = NOTIFICATION_TYPES
        resp = await self._response(profile, path_for(feed), params)
        raw = resp.json() or []
        assert isinstance(raw, list)
        items = [self.parse(feed, r) for r in raw]
        cursor = raw[-1]["id"] if raw else None
        if not self.cursor_in_cache(feed):
            m = LINK_NEXT.search(resp.headers.get("link", ""))
            cursor = m.group(1) if m else None
        return Page(raw, items, cursor)

    async def sources(self, profile: Profile) -> list[FeedSource]:
        out: list[FeedSource] = []
        for lst in await self._get(profile, "/api/v1/lists", {}) or []:
            out.append(FeedSource("list", f"list:{lst['id']}", lst.get("title") or lst["id"],
                                  _("List")))
        for tag in await self._get(profile, "/api/v1/followed_tags", {}) or []:
            out.append(FeedSource("tag", f"tag:{tag['name']}", f"#{tag['name']}",
                                  _("Followed hashtag")))
        out.append(FeedSource("bookmarks", "bookmarks", _("Bookmarks")))
        out.append(FeedSource("favourites", "favourites", _("Favourites")))
        return out

    async def fetch_marker(self, profile: Profile, feed: str) -> str | None:
        if feed not in (HOME, NOTIFICATIONS):
            return None
        try:
            data = await self._get(profile, "/api/v1/markers", {"timeline[]": [feed]})
        except PlatformError:
            return None
        marker = data.get(feed) if isinstance(data, dict) else None
        return str(marker["last_read_id"]) if marker and marker.get("last_read_id") else None

    async def push_marker(self, profile: Profile, feed: str, item_id: str) -> None:
        if feed not in (HOME, NOTIFICATIONS):
            return
        try:
            await self.platform._api(profile, "POST", "/api/v1/markers",
                                     form={f"{feed}[last_read_id]": item_id})
        except PlatformError:
            pass

    # -- Handeln ------------------------------------------------------------
    def patch_raw(self, feed: str, raw: dict, post: FeedPost) -> None:
        status = raw.get("reblog") or (raw.get("status") if "type" in raw else None) or raw
        status.update(favourited=post.favourited, reblogged=post.boosted,
                      bookmarked=post.bookmarked, favourites_count=post.likes,
                      reblogs_count=post.boosts)

    async def act(self, profile: Profile, post: FeedPost, action: str) -> dict[str, str | None]:
        if action not in ACTIONS:
            raise ValueError(action)
        verb = {"boost": "reblog", "unboost": "unreblog"}.get(action, action)
        await self.platform._api(profile, "POST", f"/api/v1/statuses/{post.ref}/{verb}")
        return {}

    async def relationship(self, profile: Profile, account: FeedAccount) -> Relationship:
        resp = await self.platform._api(profile, "GET", "/api/v1/accounts/relationships",
                                        params={"id[]": [account.id]})
        data = (resp.json() or [{}])[0]
        return _relationship(data)

    async def set_relationship(self, profile: Profile, account: FeedAccount, action: str,
                               current: Relationship) -> Relationship:
        if action not in RELATIONS:
            raise ValueError(action)
        resp = await self.platform._api(profile, "POST", f"/api/v1/accounts/{account.id}/{action}")
        return _relationship(resp.json() or {})


def _relationship(data: dict) -> Relationship:
    return Relationship(following=bool(data.get("following")),
                        followed_by=bool(data.get("followed_by")),
                        requested=bool(data.get("requested")), muted=bool(data.get("muting")),
                        blocking=bool(data.get("blocking")))
