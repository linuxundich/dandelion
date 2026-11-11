# SPDX-License-Identifier: GPL-3.0-or-later
"""Bluesky lesen: Home (Follows) und Benachrichtigungen über XRPC.

Bluesky liefert Text mit Facets (Byte-Bereiche für Links, Erwähnungen,
Hashtags) statt HTML. Der Reader macht daraus direkt Pango-Markup.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from gettext import gettext as _

from ..core.models import Profile
from ..platforms.base import PlatformError
from ..platforms.bluesky import Bluesky, post_url
from .base import (
    HOME,
    NOTIFICATIONS,
    FeedAccount,
    FeedCard,
    FeedItem,
    FeedMedia,
    FeedPost,
    Page,
    Reader,
    norm_ts,
)

#: Bluesky-Grund → Anlass im gemeinsamen Format
REASONS = {"like": "favourite", "repost": "boost", "follow": "follow", "mention": "mention",
           "reply": "reply", "quote": "quote"}
#: Labels, hinter denen ein Beitrag zugeklappt wird
HIDDEN_LABELS = {"porn": "adult content", "sexual": "sexual content", "nudity": "nudity",
                 "graphic-media": "graphic media", "gore": "graphic media"}


def facets_markup(text: str, facets: list[dict] | None) -> str:
    """Text mit Facets → Pango-Markup (Links, Erwähnungen, Hashtags)."""
    data = text.encode("utf-8")
    spans: list[tuple[int, int, str]] = []
    for facet in facets or []:
        idx = facet.get("index") or {}
        start, end = idx.get("byteStart", -1), idx.get("byteEnd", -1)
        if not 0 <= start < end <= len(data):
            continue
        uri = None
        for feat in facet.get("features", []):
            kind = feat.get("$type", "")
            if kind.endswith("#link"):
                uri = feat.get("uri")
            elif kind.endswith("#mention"):
                uri = f"https://bsky.app/profile/{feat.get('did', '')}"
            elif kind.endswith("#tag"):
                uri = f"https://bsky.app/hashtag/{feat.get('tag', '')}"
        if uri and uri.startswith(("http://", "https://")):
            spans.append((start, end, uri))
    out: list[str] = []
    pos = 0
    for start, end, uri in sorted(spans):
        if start < pos:
            continue                       # überlappende Facets überspringen
        out.append(html.escape(data[pos:start].decode("utf-8", "replace"), quote=False))
        label = html.escape(data[start:end].decode("utf-8", "replace"), quote=False)
        out.append(f'<a href="{html.escape(uri, quote=True)}">{label}</a>')
        pos = end
    out.append(html.escape(data[pos:].decode("utf-8", "replace"), quote=False))
    return "".join(out)


def _account(data: dict) -> FeedAccount:
    handle = data.get("handle", "")
    return FeedAccount(id=data.get("did", ""), acct=handle,
                       display_name=data.get("displayName") or "", avatar_url=data.get("avatar"),
                       url=f"https://bsky.app/profile/{handle}")


def _labels(*sources: dict) -> list[str]:
    out: list[str] = []
    for src in sources:
        for label in src.get("labels") or []:
            val = label.get("val", "")
            if val in HIDDEN_LABELS and val not in out:
                out.append(val)
    return out


def _apply_embed(post: FeedPost, embed: dict | None) -> None:
    """Medien, Linkkarte und Zitat aus der Ansicht (`…#view`) eines Beitrags."""
    if not embed:
        return
    kind = embed.get("$type", "")
    if kind.startswith("app.bsky.embed.recordWithMedia"):
        _apply_embed(post, embed.get("media"))
        _apply_embed(post, {"$type": "app.bsky.embed.record#view", **(embed.get("record") or {})})
    elif kind.startswith("app.bsky.embed.images"):
        post.media += [FeedMedia("image", i.get("fullsize", ""), i.get("thumb"), i.get("alt") or "")
                       for i in embed.get("images", [])]
    elif kind.startswith("app.bsky.embed.video"):
        post.media.append(FeedMedia("video", embed.get("playlist", ""), embed.get("thumbnail"),
                                    embed.get("alt") or ""))
    elif kind.startswith("app.bsky.embed.external"):
        ext = embed.get("external") or {}
        if ext.get("uri"):
            post.card = FeedCard(ext["uri"], ext.get("title") or ext["uri"],
                                 ext.get("description") or "", ext.get("thumb"))
    elif kind.startswith("app.bsky.embed.record"):
        rec = embed.get("record") or {}
        if rec.get("$type", "").endswith("viewRecord") and rec.get("author"):
            value = rec.get("value") or {}
            post.quote = FeedPost(
                id=rec.get("uri", ""), network="bluesky", account=_account(rec["author"]),
                created_at=value.get("createdAt") or rec.get("indexedAt") or "",
                markup=facets_markup(value.get("text", ""), value.get("facets")),
                url=post_url(rec["author"].get("handle", ""), rec.get("uri", "")))


def parse_post_view(view: dict, repost_by: dict | None = None) -> FeedPost:
    record = view.get("record") or {}
    author = view.get("author") or {}
    post = FeedPost(
        id=view.get("uri", ""), network="bluesky", account=_account(author),
        created_at=view.get("indexedAt") or record.get("createdAt") or "",
        markup=facets_markup(record.get("text", ""), record.get("facets")),
        url=post_url(author.get("handle", ""), view.get("uri", "")),
        language=(record.get("langs") or [None])[0],
        replies=int(view.get("replyCount") or 0), boosts=int(view.get("repostCount") or 0),
        likes=int(view.get("likeCount") or 0))
    labels = _labels(view, author)
    if labels:
        post.sensitive = True
        post.spoiler = _("Content label: {label}").format(label=HIDDEN_LABELS[labels[0]])
    _apply_embed(post, view.get("embed"))
    if repost_by:
        post.boosted_by = _account(repost_by)
    return post


def parse_feed_item(raw: dict) -> FeedPost:
    reason = raw.get("reason") or {}
    by = reason.get("by") if reason.get("$type", "").endswith("reasonRepost") else None
    post = parse_post_view(raw["post"], by)
    if by:
        post.id = f"{post.id}|{by.get('did', '')}"
        post.created_at = reason.get("indexedAt") or post.created_at
    return post


def parse_notification(raw: dict, subjects: dict[str, dict]) -> FeedPost:
    reason = REASONS.get(raw.get("reason", ""), "other")
    record = raw.get("record") or {}
    actor = _account(raw.get("author") or {})
    created = raw.get("indexedAt") or record.get("createdAt") or ""
    if reason in ("mention", "reply", "quote"):
        post = FeedPost(
            id=raw["uri"], network="bluesky", account=actor, created_at=created,
            markup=facets_markup(record.get("text", ""), record.get("facets")),
            url=post_url(actor.acct, raw["uri"]), reason=reason)
        emb = record.get("embed") or {}
        images = emb.get("images") or (emb.get("media") or {}).get("images") or []
        post.media = [FeedMedia("image", "", None, i.get("alt") or "") for i in images]
        return post
    subject = subjects.get(raw.get("reasonSubject") or "")
    return FeedPost(id=raw["uri"], network="bluesky", account=actor, created_at=created,
                    reason=reason, subject=parse_post_view(subject) if subject else None)


class BlueskyReader(Reader):
    network = "bluesky"
    feeds = (HOME, NOTIFICATIONS)
    cursor_is_id = False

    def __init__(self, platform: Bluesky) -> None:
        self.platform = platform

    def parse(self, feed: str, raw: dict) -> FeedItem:
        if feed == NOTIFICATIONS:
            return parse_notification(raw, raw.get("_subjects") or {})
        return parse_feed_item(raw)

    def key(self, feed: str, raw: dict) -> tuple[str, str]:
        if feed == NOTIFICATIONS:
            return raw["uri"], norm_ts(raw.get("indexedAt") or "")
        reason = raw.get("reason") or {}
        post = raw["post"]
        if reason.get("$type", "").endswith("reasonRepost"):
            return (f"{post.get('uri', '')}|{(reason.get('by') or {}).get('did', '')}",
                    norm_ts(reason.get("indexedAt") or ""))
        return post.get("uri", ""), norm_ts(post.get("indexedAt") or "")

    async def fetch(self, profile: Profile, feed: str, *, cursor: str | None = None,
                    limit: int = 40) -> Page:
        params: dict[str, object] = {"limit": limit, "cursor": cursor}
        if feed == NOTIFICATIONS:
            data = (await self.platform._xrpc(
                profile, "GET", "app.bsky.notification.listNotifications", params=params)).json()
            raw = data.get("notifications", [])
            subjects = await self._subjects(profile, raw)
            for r in raw:
                r["_subjects"] = {u: subjects[u] for u in [r.get("reasonSubject")] if u in subjects}
        else:
            data = (await self.platform._xrpc(
                profile, "GET", "app.bsky.feed.getTimeline", params=params)).json()
            raw = data.get("feed", [])
        return Page(raw, [self.parse(feed, r) for r in raw], data.get("cursor"))

    async def _subjects(self, profile: Profile, notifications: list[dict]) -> dict[str, dict]:
        """Beiträge, auf die sich Likes und Reposts beziehen (höchstens 25 je Anfrage)."""
        uris = list(dict.fromkeys(
            n["reasonSubject"] for n in notifications
            if n.get("reason") in ("like", "repost") and n.get("reasonSubject")
            and "/app.bsky.feed.post/" in n["reasonSubject"]))[:25]
        if not uris:
            return {}
        try:
            data = (await self.platform._xrpc(
                profile, "GET", "app.bsky.feed.getPosts", params={"uris": uris})).json()
        except PlatformError:
            return {}
        return {p["uri"]: p for p in data.get("posts", [])}

    async def push_marker(self, profile: Profile, feed: str, item_id: str) -> None:
        if feed != NOTIFICATIONS:
            return
        try:
            await self.platform._xrpc(
                profile, "POST", "app.bsky.notification.updateSeen",
                json={"seenAt": datetime.now(UTC).isoformat(timespec="milliseconds")
                      .replace("+00:00", "Z")})
        except PlatformError:
            pass
