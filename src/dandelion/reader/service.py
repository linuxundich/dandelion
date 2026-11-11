# SPDX-License-Identifier: GPL-3.0-or-later
"""Dienst für das Deck: wählt den Reader je Netzwerk, füllt den Cache."""

from __future__ import annotations

from ..core.models import Profile
from ..core.store import Store
from ..platforms import Registry
from ..platforms.mastodon import Mastodon
from .base import FeedPost, Reader
from .cache import KEEP_PER_FEED, FeedCache
from .mastodon import MastodonReader

HOME = "home"
PAGE = 40


class ReaderService:
    def __init__(self, store: Store, registry: Registry) -> None:
        self.store = store
        self.registry = registry
        self.cache = FeedCache(store)
        self._readers: dict[str, Reader] = {}

    def reader_for(self, profile: Profile) -> Reader | None:
        """Der Reader des Netzwerks oder `None`, wenn es dort nichts zu lesen gibt."""
        if profile.platform == "mastodon":
            if "mastodon" not in self._readers:
                platform = self.registry.get("mastodon")
                assert isinstance(platform, Mastodon)
                self._readers["mastodon"] = MastodonReader(platform)
            return self._readers["mastodon"]
        return None

    def can_read(self, profile: Profile) -> bool:
        return profile.platform == "mastodon"

    def cached_home(self, profile: Profile) -> list[FeedPost]:
        reader = self.reader_for(profile)
        if reader is None or profile.id is None:
            return []
        return [reader.parse(r) for r in self.cache.load(profile.id, HOME, KEEP_PER_FEED)]

    async def refresh_home(self, profile: Profile) -> list[FeedPost]:
        """Holt die neuesten Beiträge und gibt die ganze Spalte zurück."""
        reader = self.reader_for(profile)
        if reader is None or profile.id is None:
            return []
        raw, _posts = await reader.fetch_home(profile, limit=PAGE)
        self.cache.save(profile.id, HOME, raw)
        return self.cached_home(profile)

    async def load_older(self, profile: Profile) -> list[FeedPost]:
        reader = self.reader_for(profile)
        if reader is None or profile.id is None:
            return []
        oldest = self.cache.oldest_id(profile.id, HOME)
        raw, _posts = await reader.fetch_home(profile, before=oldest, limit=PAGE)
        self.cache.save(profile.id, HOME, raw)
        return self.cached_home(profile)
