# SPDX-License-Identifier: GPL-3.0-or-later
"""Scheduler-Kern: fällige Beiträge senden, verpasste erkennen.

Derselbe Ablauf läuft in drei Situationen:
  - als Kurzläufer `dandelion --run-due`, ausgelöst vom systemd-User-Timer,
  - im Hintergrundprozess unter Flatpak (Background-Portal),
  - im laufenden Fenster als Ticker.
Doppelversand verhindert `Store.claim_post()`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .models import Post, PostState
from .publisher import AlreadySending, Publisher
from .store import Store

log = logging.getLogger(__name__)


class MissedPolicy(StrEnum):
    ASK = "ask"
    SEND = "send"
    DISCARD = "discard"


def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("Zeitpunkt ohne Zeitzone")
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


@dataclass
class RunResult:
    sent: list[Post] = field(default_factory=list)
    late: list[Post] = field(default_factory=list)      # verspätet, aber gesendet
    missed: list[Post] = field(default_factory=list)    # nicht gesendet, wartet auf Entscheidung
    next_due: datetime | None = None


class Scheduler:
    def __init__(self, store: Store, publisher: Publisher, *,
                 policy: MissedPolicy = MissedPolicy.ASK,
                 grace: timedelta = timedelta(minutes=15),
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self.store = store
        self.publisher = publisher
        self.policy = policy
        self.grace = grace
        self.clock = clock

    def next_due(self) -> datetime | None:
        value = self.store.next_scheduled_at()
        return parse_iso(value) if value else None

    async def run_due(self) -> RunResult:
        result = RunResult()
        now = self.clock()
        for post_id in self.store.due_post_ids(to_utc_iso(now)):
            post = self.store.load_post(post_id)
            if post is None or not post.scheduled_at:
                continue
            lateness = now - parse_iso(post.scheduled_at)
            late = lateness > self.grace
            if late and self.policy != MissedPolicy.SEND:
                self.store.set_post_schedule(post_id, PostState.MISSED, post.scheduled_at)
                post.state = PostState.MISSED
                result.missed.append(post)
                log.info("Beitrag %s verpasst (%s zu spät)", post_id, lateness)
                continue
            try:
                sent = await self.publisher.send(post_id)
            except AlreadySending:
                continue
            (result.late if late else result.sent).append(sent)
        result.next_due = self.next_due()
        return result

    def missed_posts(self) -> list[Post]:
        posts = []
        for pid in self.store.post_ids([PostState.MISSED], order="scheduled_at"):
            post = self.store.load_post(pid)
            if post:
                posts.append(post)
        return posts
