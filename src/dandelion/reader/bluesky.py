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
    ACTIONS,
    RELATIONS,
    FeedAccount,
    FeedCard,
    FeedItem,
    FeedMedia,
    FeedPost,
    FeedSource,
    Page,
    Reader,
    Relationship,
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
        likes=int(view.get("likeCount") or 0),
        ref=view.get("uri", ""), cid=view.get("cid"))
    viewer = view.get("viewer") or {}
    post.like_uri, post.repost_uri = viewer.get("like"), viewer.get("repost")
    post.favourited, post.boosted = bool(post.like_uri), bool(post.repost_uri)
    post.bookmarked = bool(viewer.get("bookmarked"))
    parent = (record.get("reply") or {}).get("root")
    if parent and parent.get("uri") and parent.get("cid"):
        post.root_ref = (parent["uri"], parent["cid"])
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
            url=post_url(actor.acct, raw["uri"]), reason=reason, ref=raw["uri"], cid=raw.get("cid"))
        root = (record.get("reply") or {}).get("root") or {}
        if root.get("uri") and root.get("cid"):
            post.root_ref = (root["uri"], root["cid"])
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

    def cursor_in_cache(self, feed: str) -> bool:
        return False

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
            data = await self._feed(profile, feed, params)
            raw = data["items"]
        return Page(raw, [self.parse(feed, r) for r in raw], data.get("cursor"))

    async def _feed(self, profile: Profile, feed: str, params: dict) -> dict:
        """Beiträge einer Liste: Home, Feed, Liste, Hashtag-Suche, Lesezeichen oder Likes.

        Gibt `{"items": [{"post": …}, …], "cursor": …}` zurück.
        """
        call = self.platform._xrpc
        kind, _sep, key = feed.partition(":")
        if feed == HOME:
            data = (await call(profile, "GET", "app.bsky.feed.getTimeline", params=params)).json()
            return {"items": data.get("feed", []), "cursor": data.get("cursor")}
        if kind == "feed":
            data = (await call(profile, "GET", "app.bsky.feed.getFeed",
                               params={**params, "feed": key})).json()
            return {"items": data.get("feed", []), "cursor": data.get("cursor")}
        if kind == "list":
            data = (await call(profile, "GET", "app.bsky.feed.getListFeed",
                               params={**params, "list": key})).json()
            return {"items": data.get("feed", []), "cursor": data.get("cursor")}
        if kind == "tag":
            data = (await call(profile, "GET", "app.bsky.feed.searchPosts",
                               params={**params, "q": f"#{key}", "sort": "latest"})).json()
            return {"items": [{"post": p} for p in data.get("posts", [])],
                    "cursor": data.get("cursor")}
        if feed == "bookmarks":
            data = (await call(profile, "GET", "app.bsky.bookmark.getBookmarks",
                               params=params)).json()
            return {"items": [{"post": b["item"]} for b in data.get("bookmarks", [])
                              if (b.get("item") or {}).get("record")],
                    "cursor": data.get("cursor")}
        if feed == "favourites":
            data = (await call(profile, "GET", "app.bsky.feed.getActorLikes",
                               params={**params, "actor": profile.remote_id})).json()
            return {"items": data.get("feed", []), "cursor": data.get("cursor")}
        raise ValueError(feed)

    async def sources(self, profile: Profile) -> list[FeedSource]:
        out: list[FeedSource] = []
        call = self.platform._xrpc
        try:
            prefs = (await call(profile, "GET", "app.bsky.actor.getPreferences")).json()
        except PlatformError:
            prefs = {}
        saved: list[dict] = []
        for pref in prefs.get("preferences", []):
            if pref.get("$type", "").endswith("savedFeedsPrefV2"):
                saved = pref.get("items", [])
        feed_uris = [i["value"] for i in saved if i.get("type") == "feed"]
        names: dict[str, str] = {}
        if feed_uris:
            try:
                gens = (await call(profile, "GET", "app.bsky.feed.getFeedGenerators",
                                   params={"feeds": feed_uris})).json()
                names = {g["uri"]: g.get("displayName", "") for g in gens.get("feeds", [])}
            except PlatformError:
                pass
        for uri in feed_uris:
            out.append(FeedSource("feed", f"feed:{uri}", names.get(uri) or uri, _("Feed")))
        for item in saved:
            if item.get("type") != "list":
                continue
            title = item["value"]
            try:
                data = (await call(profile, "GET", "app.bsky.graph.getList",
                                   params={"list": item["value"], "limit": 1})).json()
                title = (data.get("list") or {}).get("name") or title
            except PlatformError:
                pass
            out.append(FeedSource("list", f"list:{item['value']}", title, _("List")))
        out.append(FeedSource("bookmarks", "bookmarks", _("Bookmarks")))
        out.append(FeedSource("favourites", "favourites", _("Likes")))
        return out

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

    # -- Handeln ------------------------------------------------------------
    def patch_raw(self, feed: str, raw: dict, post: FeedPost) -> None:
        view = raw.get("post")
        if not view:
            return
        view["likeCount"], view["repostCount"] = post.likes, post.boosts
        view["viewer"] = {**(view.get("viewer") or {}), "like": post.like_uri,
                          "repost": post.repost_uri, "bookmarked": post.bookmarked}

    async def _create(self, profile: Profile, collection: str, record: dict) -> str:
        sess = await self.platform._session(profile)
        record = {"$type": collection, "createdAt": _now(), **record}
        resp = await self.platform._xrpc(profile, "POST", "com.atproto.repo.createRecord", json={
            "repo": sess["did"], "collection": collection, "record": record})
        return resp.json()["uri"]

    async def _delete(self, profile: Profile, collection: str, uri: str | None) -> None:
        if not uri:
            return
        sess = await self.platform._session(profile)
        await self.platform._xrpc(profile, "POST", "com.atproto.repo.deleteRecord", json={
            "repo": sess["did"], "collection": collection, "rkey": uri.rsplit("/", 1)[-1]})

    async def act(self, profile: Profile, post: FeedPost, action: str) -> dict[str, str | None]:
        if action not in ACTIONS:
            raise ValueError(action)
        subject = {"subject": {"uri": post.ref, "cid": post.cid}}
        if action == "favourite":
            return {"like_uri": await self._create(profile, "app.bsky.feed.like", subject)}
        if action == "unfavourite":
            await self._delete(profile, "app.bsky.feed.like", post.like_uri)
            return {"like_uri": None}
        if action == "boost":
            return {"repost_uri": await self._create(profile, "app.bsky.feed.repost", subject)}
        if action == "unboost":
            await self._delete(profile, "app.bsky.feed.repost", post.repost_uri)
            return {"repost_uri": None}
        nsid = "createBookmark" if action == "bookmark" else "deleteBookmark"
        body = {"uri": post.ref, "cid": post.cid} if action == "bookmark" else {"uri": post.ref}
        await self.platform._xrpc(profile, "POST", f"app.bsky.bookmark.{nsid}", json=body)
        return {}

    async def relationship(self, profile: Profile, account: FeedAccount) -> Relationship:
        data = (await self.platform._xrpc(profile, "GET", "app.bsky.actor.getProfile",
                                          params={"actor": account.id})).json()
        viewer = data.get("viewer") or {}
        return Relationship(following=bool(viewer.get("following")),
                            followed_by=bool(viewer.get("followedBy")),
                            muted=bool(viewer.get("muted")), blocking=bool(viewer.get("blocking")),
                            follow_uri=viewer.get("following"), block_uri=viewer.get("blocking"))

    async def set_relationship(self, profile: Profile, account: FeedAccount, action: str,
                               current: Relationship) -> Relationship:
        if action not in RELATIONS:
            raise ValueError(action)
        rel = Relationship(**vars(current))
        if action == "follow":
            rel.follow_uri = await self._create(profile, "app.bsky.graph.follow",
                                                {"subject": account.id})
            rel.following = True
        elif action == "unfollow":
            await self._delete(profile, "app.bsky.graph.follow", rel.follow_uri)
            rel.follow_uri, rel.following = None, False
        elif action in ("mute", "unmute"):
            await self.platform._xrpc(
                profile, "POST", f"app.bsky.graph.{action}Actor", json={"actor": account.id})
            rel.muted = action == "mute"
        elif action == "block":
            rel.block_uri = await self._create(profile, "app.bsky.graph.block",
                                               {"subject": account.id})
            rel.blocking = True
        else:
            await self._delete(profile, "app.bsky.graph.block", rel.block_uri)
            rel.block_uri, rel.blocking = None, False
        return rel


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
