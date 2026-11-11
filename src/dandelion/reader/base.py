# SPDX-License-Identifier: GPL-3.0-or-later
"""Gemeinsame Schnittstelle zum Lesen: ein Beitragsformat für alle Netzwerke.

Die Spalten im Deck kennen nur `FeedPost`. Wie ein Netzwerk seine Beiträge
liefert (Mastodon: REST + HTML, Bluesky: XRPC + Facets), steckt im jeweiligen
Reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..core.models import Profile
from ..platforms.base import PlatformError


class ReadScopeMissing(PlatformError):
    """Das gespeicherte Token darf nicht lesen (Anmeldung vor dem Deck)."""


@dataclass
class FeedAccount:
    id: str
    acct: str                 # Mastodon: user@server, lokal nur user
    display_name: str
    avatar_url: str | None = None
    url: str = ""

    @property
    def name(self) -> str:
        return self.display_name or self.acct


@dataclass
class FeedMedia:
    kind: str                 # image | video | gifv | audio | other
    url: str
    preview_url: str | None = None
    alt: str = ""


@dataclass
class FeedCard:
    url: str
    title: str
    description: str = ""
    image_url: str | None = None


@dataclass
class FeedPost:
    id: str
    network: str
    account: FeedAccount
    created_at: str           # ISO 8601
    html: str = ""            # Inhalt des Netzwerks, noch nicht aufbereitet
    spoiler: str = ""         # Inhaltswarnung, leer wenn keine
    sensitive: bool = False
    url: str = ""
    language: str | None = None
    media: list[FeedMedia] = field(default_factory=list)
    card: FeedCard | None = None
    boosted_by: FeedAccount | None = None
    replies: int = 0
    boosts: int = 0
    likes: int = 0
    has_poll: bool = False


class Reader(ABC):
    """Liest Beiträge eines Profils."""

    network: str

    @abstractmethod
    async def fetch_home(self, profile: Profile, *, before: str | None = None,
                         limit: int = 40) -> tuple[list[dict], list[FeedPost]]:
        """Holt die Home-Timeline (neueste zuerst).

        `before` ist die ID des ältesten bekannten Beitrags und lädt ältere
        nach. Gibt die Rohdaten (für den Cache) und die geparsten Beiträge zurück.
        """

    @abstractmethod
    def parse(self, raw: dict) -> FeedPost:
        """Wandelt Rohdaten aus dem Cache oder von der Schnittstelle um."""
