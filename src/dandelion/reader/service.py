# SPDX-License-Identifier: GPL-3.0-or-later
"""Dienst für das Deck: wählt den Reader je Netzwerk, füllt Cache und Lesestände."""

from __future__ import annotations

from uuid import uuid4

from ..core.models import Profile, TargetPart
from ..core.store import Store
from ..platforms import Registry
from ..platforms.bluesky import Bluesky
from ..platforms.mastodon import Mastodon
from ..platforms.base import Composition, PlatformError
from .base import (
    HOME,
    MESSAGES,
    NOTIFICATIONS,
    FeedAccount,
    FeedConversation,
    FeedItem,
    FeedPost,
    Reader,
    Relationship,
)
from .bluesky import BlueskyReader
from .cache import KEEP_PER_FEED, FeedCache
from .mastodon import MastodonReader

PAGE = 40
UNREAD_FEEDS = (HOME, NOTIFICATIONS, MESSAGES)


class ReaderService:
    def __init__(self, store: Store, registry: Registry) -> None:
        self.store = store
        self.registry = registry
        self.cache = FeedCache(store)
        self._readers: dict[str, Reader] = {}
        self._cursors: dict[tuple[int, str], str | None] = {}

    # -- Reader -------------------------------------------------------------
    def reader_for(self, profile: Profile) -> Reader | None:
        """Der Reader des Netzwerks oder `None`, wenn es dort nichts zu lesen gibt."""
        if profile.platform not in self._readers:
            platform = self.registry.get(profile.platform) if profile.platform in self.registry else None
            if isinstance(platform, Mastodon):
                self._readers[profile.platform] = MastodonReader(platform)
            elif isinstance(platform, Bluesky):
                self._readers[profile.platform] = BlueskyReader(platform)
            else:
                return None
        return self._readers[profile.platform]

    def can_read(self, profile: Profile) -> bool:
        return profile.platform in ("mastodon", "bluesky")

    def feeds(self, profile: Profile) -> tuple[str, ...]:
        reader = self.reader_for(profile)
        return reader.feeds if reader else ()

    # -- Einträge -----------------------------------------------------------
    def cached(self, profile: Profile, feed: str) -> list[FeedItem]:
        reader = self.reader_for(profile)
        if reader is None or profile.id is None:
            return []
        return [reader.parse(feed, r) for r in self.cache.load(profile.id, feed, KEEP_PER_FEED)]

    def _store(self, reader: Reader, profile: Profile, feed: str, raw: list[dict]) -> None:
        keyed = [(*reader.key(feed, r), r) for r in raw]
        self.cache.save(profile.id, feed, keyed)  # type: ignore[arg-type]

    async def refresh(self, profile: Profile, feed: str) -> list[FeedItem]:
        """Holt die neuesten Einträge und gibt den ganzen Cache des Feeds zurück."""
        reader = self.reader_for(profile)
        if reader is None or profile.id is None:
            return []
        page = await reader.fetch(profile, feed, limit=PAGE)
        self._store(reader, profile, feed, page.raw)
        if not reader.cursor_is_id and (profile.id, feed) not in self._cursors:
            self._cursors[(profile.id, feed)] = page.cursor
        await self._init_marker(reader, profile, feed)
        return self.cached(profile, feed)

    async def load_older(self, profile: Profile, feed: str) -> list[FeedItem]:
        reader = self.reader_for(profile)
        if reader is None or profile.id is None:
            return []
        key = (profile.id, feed)
        if reader.cursor_is_id:
            cursor = self.cache.oldest_id(profile.id, feed)
        else:
            if self._cursors.get(key) is None:       # nach einem Neustart: erst Seite eins
                first = await reader.fetch(profile, feed, limit=PAGE)
                self._store(reader, profile, feed, first.raw)
                self._cursors[key] = first.cursor
            cursor = self._cursors.get(key)
        if cursor is None:
            return self.cached(profile, feed)
        page = await reader.fetch(profile, feed, cursor=cursor, limit=PAGE)
        self._store(reader, profile, feed, page.raw)
        if not reader.cursor_is_id:
            self._cursors[key] = page.cursor
        return self.cached(profile, feed)

    # -- Lesestand ----------------------------------------------------------
    async def _init_marker(self, reader: Reader, profile: Profile, feed: str) -> None:
        """Erster Abruf: Lesestand vom Server oder „alles bisher gilt als gelesen“."""
        pid = profile.id
        if pid is None or feed == MESSAGES or self.cache.marker(pid, feed) is not None:
            return
        server_id = await reader.fetch_marker(profile, feed)
        ts = self.cache.created_at_of(pid, feed, server_id) if server_id else None
        if ts is None:
            newest = self.cache.newest(pid, feed)
            ts = newest[1] if newest else None
        if ts:
            self.cache.set_marker(pid, feed, ts)

    def marker(self, profile: Profile, feed: str) -> str | None:
        return self.cache.marker(profile.id, feed) if profile.id is not None else None

    def unread(self, profile: Profile, feed: str) -> int:
        pid = profile.id
        if pid is None:
            return 0
        if feed == MESSAGES:
            return sum(1 for c in self.cached(profile, feed)
                       if isinstance(c, FeedConversation) and c.unread)
        ts = self.cache.marker(pid, feed)
        return self.cache.count_newer(pid, feed, ts) if ts else 0

    def unread_total(self, profile: Profile) -> int:
        return sum(self.unread(profile, f) for f in self.feeds(profile))

    async def mark_read(self, profile: Profile, feed: str) -> None:
        """Setzt den Lesestand auf den neuesten Eintrag und meldet ihn dem Netzwerk."""
        reader = self.reader_for(profile)
        pid = profile.id
        if reader is None or pid is None or feed == MESSAGES:
            return
        newest = self.cache.newest(pid, feed)
        if newest is None:
            return
        self.cache.set_marker(pid, feed, newest[1])
        await reader.push_marker(profile, feed, newest[0])

    # -- Handeln ------------------------------------------------------------
    async def act(self, profile: Profile, post: FeedPost, action: str,
                  feed: str | None = None) -> None:
        """Favorit, Boost oder Lesezeichen; passt den Beitrag und, mit `feed`, den Cache an."""
        reader = self._need_reader(profile)
        changes = await reader.act(profile, post, action)
        for field_name, value in changes.items():
            setattr(post, field_name, value)
        if feed and profile.id is not None:
            self.cache.update(profile.id, feed, post.id,
                              lambda raw: reader.patch_raw(feed, raw, post))

    async def relationship(self, profile: Profile, account: FeedAccount) -> Relationship:
        return await self._need_reader(profile).relationship(profile, account)

    async def set_relationship(self, profile: Profile, account: FeedAccount, action: str,
                               current: Relationship) -> Relationship:
        return await self._need_reader(profile).set_relationship(profile, account, action, current)

    async def send(self, profile: Profile, comp: Composition, *, reply_to: FeedPost | None = None,
                   quote: FeedPost | None = None) -> TargetPart:
        """Schickt einen Beitrag, eine Antwort oder ein Zitat von diesem Profil."""
        platform = self.registry.get(profile.platform)
        parent = root = None
        if reply_to is not None:
            parent = TargetPart(idx=0, remote_id=reply_to.ref, remote_cid=reply_to.cid)
            if reply_to.root_ref:
                root = TargetPart(idx=0, remote_id=reply_to.root_ref[0],
                                  remote_cid=reply_to.root_ref[1])
        kwargs = {}
        if quote is not None:
            if profile.platform != "bluesky":
                raise PlatformError("quotes are only supported on Bluesky")
            kwargs["quote"] = TargetPart(idx=0, remote_id=quote.ref, remote_cid=quote.cid)
        return await platform.post(profile, comp, [], reply_to=parent, root=root or parent,
                                   idempotency_key=uuid4().hex, **kwargs)

    def can_quote(self, profile: Profile) -> bool:
        return profile.platform == "bluesky"

    def _need_reader(self, profile: Profile) -> Reader:
        reader = self.reader_for(profile)
        if reader is None:
            raise PlatformError("not supported")
        return reader
