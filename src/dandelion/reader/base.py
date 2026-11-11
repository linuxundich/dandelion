# SPDX-License-Identifier: GPL-3.0-or-later
"""Gemeinsame Schnittstelle zum Lesen: ein Beitragsformat für alle Netzwerke.

Die Spalten im Deck kennen nur `FeedPost` und `FeedConversation`. Wie ein
Netzwerk seine Beiträge liefert (Mastodon: REST + HTML, Bluesky: XRPC +
Facets), steckt im jeweiligen Reader.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..core.models import Profile
from ..platforms.base import PlatformError

HOME, NOTIFICATIONS, MESSAGES = "home", "notifications", "messages"

#: Benachrichtigungen, die wie ein normaler Beitrag aussehen (der Absender ist der Autor)
POST_REASONS = ("mention", "reply", "quote", "status", "update")


class ReadScopeMissing(PlatformError):
    """Das gespeicherte Token darf nicht lesen (Anmeldung vor dem Deck)."""


def norm_ts(iso: str) -> str:
    """Zeitstempel in UTC als sortierbarer Text, unabhängig vom Format des Netzwerks."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S")


@dataclass
class FeedAccount:
    id: str
    acct: str                 # Mastodon: user@server, Bluesky: Handle
    display_name: str
    avatar_url: str | None = None
    url: str = ""

    @property
    def name(self) -> str:
        return self.display_name or self.acct


@dataclass
class FeedMedia:
    kind: str                 # image | video | gifv | audio | other
    url: str                  # leer, wenn das Netzwerk keine Adresse liefert
    preview_url: str | None = None
    alt: str = ""


@dataclass
class FeedCard:
    url: str
    title: str
    description: str = ""
    image_url: str | None = None


@dataclass
class FeedPoll:
    options: list[tuple[str, int]]
    votes: int = 0
    expired: bool = False
    multiple: bool = False


@dataclass
class FeedPost:
    id: str
    network: str
    account: FeedAccount
    created_at: str           # ISO 8601 des Netzwerks
    html: str = ""            # Mastodon-HTML, noch nicht aufbereitet
    markup: str | None = None # fertiges Pango-Markup (Bluesky); hat Vorrang vor `html`
    spoiler: str = ""         # Inhaltswarnung, leer wenn keine
    sensitive: bool = False
    url: str = ""
    language: str | None = None
    media: list[FeedMedia] = field(default_factory=list)
    card: FeedCard | None = None
    poll: FeedPoll | None = None
    quote: FeedPost | None = None
    boosted_by: FeedAccount | None = None
    replies: int = 0
    boosts: int = 0
    likes: int = 0
    #: Nur bei Benachrichtigungen: Anlass (mention, favourite, boost, follow, …) und Bezug
    reason: str | None = None
    subject: FeedPost | None = None

    @property
    def has_poll(self) -> bool:
        return self.poll is not None

    @property
    def sort_ts(self) -> str:
        return norm_ts(self.created_at)


@dataclass
class FeedConversation:
    id: str
    created_at: str
    accounts: list[FeedAccount]
    last: FeedPost | None = None
    unread: bool = False

    @property
    def sort_ts(self) -> str:
        return norm_ts(self.created_at)


FeedItem = FeedPost | FeedConversation


@dataclass
class Page:
    """Eine Antwort des Netzwerks: Rohdaten für den Cache, geparste Einträge, nächster Cursor."""

    raw: list[dict]
    items: list[FeedItem]
    cursor: str | None = None


class Reader(ABC):
    """Liest Beiträge eines Profils."""

    network: str
    feeds: tuple[str, ...] = (HOME,)
    #: Mastodon blättert mit der ID des ältesten Eintrags, Bluesky mit einem Cursor
    cursor_is_id: bool = True

    @abstractmethod
    async def fetch(self, profile: Profile, feed: str, *, cursor: str | None = None,
                    limit: int = 40) -> Page:
        """Holt Einträge (neueste zuerst); `cursor` lädt ältere nach."""

    @abstractmethod
    def parse(self, feed: str, raw: dict) -> FeedItem:
        """Wandelt Rohdaten aus dem Cache oder von der Schnittstelle um."""

    @abstractmethod
    def key(self, feed: str, raw: dict) -> tuple[str, str]:
        """(ID, normalisierter Zeitstempel) für den Cache."""

    async def fetch_marker(self, profile: Profile, feed: str) -> str | None:
        """ID des zuletzt gelesenen Eintrags laut Server, falls das Netzwerk das kennt."""
        return None

    async def push_marker(self, profile: Profile, feed: str, item_id: str) -> None:
        """Meldet den Lesestand dem Server, falls das Netzwerk das kennt."""
