# SPDX-License-Identifier: GPL-3.0-or-later
"""Zwischenspeicher der Timelines und Lesestände in der Dandelion-Datenbank.

Gespeichert werden die Rohdaten des Netzwerks; beim Laden werden sie neu
geparst. So überstehen Änderungen am Beitragsformat ein Update ohne Migration.
Der Lesestand ist ein Zeitstempel (normalisiert, UTC): alles, was neuer ist,
gilt als ungelesen.
"""

from __future__ import annotations

import json

from ..core.models import now_iso
from ..core.store import Store

KEEP_PER_FEED = 400


class FeedCache:
    def __init__(self, store: Store) -> None:
        self.db = store.db

    # -- Einträge -----------------------------------------------------------
    def save(self, profile_id: int, feed: str, items: list[tuple[str, str, dict]]) -> None:
        """`items`: (ID, Zeitstempel, Rohdaten)."""
        if not items:
            return
        ts = now_iso()
        self.db.execute("BEGIN")
        try:
            self.db.executemany(
                "INSERT INTO feed_item (profile_id, feed, remote_id, created_at, raw_json, fetched_at)"
                " VALUES (?,?,?,?,?,?) ON CONFLICT(profile_id, feed, remote_id)"
                " DO UPDATE SET raw_json = excluded.raw_json, fetched_at = excluded.fetched_at",
                [(profile_id, feed, rid, created, json.dumps(raw, ensure_ascii=False), ts)
                 for rid, created, raw in items])
            self.db.execute(
                "DELETE FROM feed_item WHERE profile_id = ? AND feed = ? AND remote_id NOT IN ("
                " SELECT remote_id FROM feed_item WHERE profile_id = ? AND feed = ?"
                " ORDER BY created_at DESC LIMIT ?)",
                (profile_id, feed, profile_id, feed, KEEP_PER_FEED))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def load(self, profile_id: int, feed: str, limit: int = 100) -> list[dict]:
        rows = self.db.execute(
            "SELECT raw_json FROM feed_item WHERE profile_id = ? AND feed = ?"
            " ORDER BY created_at DESC LIMIT ?", (profile_id, feed, limit))
        return [json.loads(r[0]) for r in rows]

    def oldest_id(self, profile_id: int, feed: str) -> str | None:
        row = self.db.execute(
            "SELECT remote_id FROM feed_item WHERE profile_id = ? AND feed = ?"
            " ORDER BY created_at ASC LIMIT 1", (profile_id, feed)).fetchone()
        return row[0] if row else None

    def newest(self, profile_id: int, feed: str) -> tuple[str, str] | None:
        """(ID, Zeitstempel) des neuesten Eintrags."""
        row = self.db.execute(
            "SELECT remote_id, created_at FROM feed_item WHERE profile_id = ? AND feed = ?"
            " ORDER BY created_at DESC LIMIT 1", (profile_id, feed)).fetchone()
        return (row[0], row[1]) if row else None

    def created_at_of(self, profile_id: int, feed: str, remote_id: str) -> str | None:
        row = self.db.execute(
            "SELECT created_at FROM feed_item WHERE profile_id = ? AND feed = ? AND remote_id = ?",
            (profile_id, feed, remote_id)).fetchone()
        return row[0] if row else None

    def count_newer(self, profile_id: int, feed: str, ts: str) -> int:
        return self.db.execute(
            "SELECT COUNT(*) FROM feed_item WHERE profile_id = ? AND feed = ? AND created_at > ?",
            (profile_id, feed, ts)).fetchone()[0]

    # -- Lesestand ----------------------------------------------------------
    def marker(self, profile_id: int, feed: str) -> str | None:
        row = self.db.execute(
            "SELECT read_until FROM read_marker WHERE profile_id = ? AND feed = ?",
            (profile_id, feed)).fetchone()
        return row[0] if row else None

    def set_marker(self, profile_id: int, feed: str, ts: str) -> None:
        self.db.execute(
            "INSERT INTO read_marker (profile_id, feed, read_until) VALUES (?,?,?)"
            " ON CONFLICT(profile_id, feed) DO UPDATE SET read_until = excluded.read_until"
            " WHERE excluded.read_until > read_until", (profile_id, feed, ts))
