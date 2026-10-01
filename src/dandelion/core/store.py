# SPDX-License-Identifier: GPL-3.0-or-later
"""SQLite-Ablage unter $XDG_DATA_HOME/dandelion/dandelion.db.

Alle Zugriffe laufen synchron. Die Datenbank ist lokal und klein, die
Abfragen dauern Mikrosekunden. WAL erlaubt parallele Leser (GUI und
Hintergrunddienst).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import (
    Media,
    Post,
    PostState,
    Profile,
    ProfileStatus,
    Role,
    RoleProfile,
    Target,
    TargetPart,
    TargetState,
    Variant,
    now_iso,
)

SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, str] = {
    1: """
CREATE TABLE role (
  id            INTEGER PRIMARY KEY,
  uuid          TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  emoji         TEXT,
  color         TEXT NOT NULL DEFAULT 'blue',
  avatar_path   TEXT,
  position      INTEGER NOT NULL,
  language      TEXT,
  visibility    TEXT,
  signature     TEXT NOT NULL DEFAULT '',
  ai_style      TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

CREATE TABLE profile (
  id            INTEGER PRIMARY KEY,
  uuid          TEXT NOT NULL UNIQUE,
  platform      TEXT NOT NULL,
  server        TEXT,
  remote_id     TEXT NOT NULL,
  handle        TEXT NOT NULL,
  display_name  TEXT NOT NULL DEFAULT '',
  label         TEXT NOT NULL DEFAULT '',
  avatar_url    TEXT,
  auth_method   TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'ok',
  status_detail TEXT NOT NULL DEFAULT '',
  token_expires_at TEXT,
  limits_json   TEXT,
  limits_fetched_at TEXT,
  options_json  TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  UNIQUE (platform, server, remote_id)
);

CREATE TABLE role_profile (
  role_id       INTEGER NOT NULL REFERENCES role(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
  preselected   INTEGER NOT NULL DEFAULT 1,
  position      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (role_id, profile_id)
);

CREATE TABLE post (
  id            INTEGER PRIMARY KEY,
  uuid          TEXT NOT NULL UNIQUE,
  role_id       INTEGER REFERENCES role(id) ON DELETE SET NULL,
  state         TEXT NOT NULL,
  body          TEXT NOT NULL DEFAULT '',
  content_warning TEXT NOT NULL DEFAULT '',
  language      TEXT,
  visibility    TEXT,
  bluesky_label TEXT,
  use_signature INTEGER NOT NULL DEFAULT 1,
  thread_mode   TEXT NOT NULL DEFAULT 'off',
  scheduled_at  TEXT,
  timezone      TEXT,
  claimed_until TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  published_at  TEXT,
  deleted_at    TEXT
);
CREATE INDEX post_due ON post(state, scheduled_at);

CREATE TABLE post_variant (
  id            INTEGER PRIMARY KEY,
  post_id       INTEGER NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  platform      TEXT NOT NULL,
  profile_id    INTEGER REFERENCES profile(id) ON DELETE CASCADE,
  body          TEXT NOT NULL,
  content_warning TEXT,
  base_hash     TEXT
);
CREATE UNIQUE INDEX post_variant_key ON post_variant(post_id, platform, IFNULL(profile_id, 0));

CREATE TABLE media (
  id            INTEGER PRIMARY KEY,
  post_id       INTEGER NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  path          TEXT NOT NULL,
  sha256        TEXT NOT NULL,
  mime          TEXT NOT NULL,
  bytes         INTEGER NOT NULL,
  width INTEGER, height INTEGER, duration_s REAL,
  alt_text      TEXT NOT NULL DEFAULT '',
  focus_x REAL, focus_y REAL
);

CREATE TABLE post_target (
  id            INTEGER PRIMARY KEY,
  post_id       INTEGER NOT NULL REFERENCES post(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
  enabled       INTEGER NOT NULL DEFAULT 1,
  state         TEXT NOT NULL DEFAULT 'pending',
  idempotency_key TEXT NOT NULL,
  attempts      INTEGER NOT NULL DEFAULT 0,
  last_error    TEXT,
  last_error_detail TEXT,
  remote_url    TEXT,
  remote_scheduled_id TEXT,
  published_at  TEXT,
  UNIQUE (post_id, profile_id)
);

CREATE TABLE post_target_part (
  target_id     INTEGER NOT NULL REFERENCES post_target(id) ON DELETE CASCADE,
  idx           INTEGER NOT NULL,
  remote_id     TEXT,
  remote_cid    TEXT,
  remote_url    TEXT,
  PRIMARY KEY (target_id, idx)
);

CREATE TABLE media_upload (
  media_id      INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  profile_id    INTEGER NOT NULL REFERENCES profile(id) ON DELETE CASCADE,
  remote_ref    TEXT NOT NULL,
  uploaded_at   TEXT NOT NULL,
  expires_at    TEXT,
  PRIMARY KEY (media_id, profile_id)
);

CREATE VIRTUAL TABLE post_fts USING fts5(body, content='post', content_rowid='id');
CREATE TRIGGER post_ai AFTER INSERT ON post BEGIN
  INSERT INTO post_fts(rowid, body) VALUES (new.id, new.body);
END;
CREATE TRIGGER post_ad AFTER DELETE ON post BEGIN
  INSERT INTO post_fts(post_fts, rowid, body) VALUES ('delete', old.id, old.body);
END;
CREATE TRIGGER post_au AFTER UPDATE OF body ON post BEGIN
  INSERT INTO post_fts(post_fts, rowid, body) VALUES ('delete', old.id, old.body);
  INSERT INTO post_fts(rowid, body) VALUES (new.id, new.body);
END;
""",
}


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = Path(base) / "dandelion"
    path.mkdir(parents=True, exist_ok=True)
    return path


def media_dir() -> Path:
    path = data_dir() / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    path = Path(base) / "dandelion"
    path.mkdir(parents=True, exist_ok=True)
    return path


class Store:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = str(path) if path is not None else str(data_dir() / "dandelion.db")
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.db.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------------
    def _migrate(self) -> None:
        cur = self.db.execute("PRAGMA user_version")
        version = cur.fetchone()[0]
        for v in range(version + 1, SCHEMA_VERSION + 1):
            self.db.execute("BEGIN")
            try:
                self._exec_script(_MIGRATIONS[v])
                self.db.execute(f"PRAGMA user_version = {v}")
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def _exec_script(self, script: str) -> None:
        # executescript() würde die offene Transaktion committen; deshalb
        # Anweisung für Anweisung (Trigger enthalten Semikolons im BEGIN…END).
        buf = ""
        for line in script.splitlines(keepends=True):
            buf += line
            if sqlite3.complete_statement(buf):
                if buf.strip():
                    self.db.execute(buf)
                buf = ""

    def transaction(self) -> "_Tx":
        return _Tx(self.db)

    # ------------------------------------------------------------------
    # Rollen
    # ------------------------------------------------------------------
    @staticmethod
    def _role(row: sqlite3.Row) -> Role:
        return Role(
            id=row["id"], uuid=row["uuid"], name=row["name"], emoji=row["emoji"] or "",
            color=row["color"], avatar_path=row["avatar_path"], position=row["position"],
            language=row["language"], visibility=row["visibility"],
            signature=row["signature"], ai_style=row["ai_style"],
        )

    def roles(self) -> list[Role]:
        rows = self.db.execute("SELECT * FROM role ORDER BY position, id")
        return [self._role(r) for r in rows]

    def role(self, role_id: int) -> Role | None:
        row = self.db.execute("SELECT * FROM role WHERE id = ?", (role_id,)).fetchone()
        return self._role(row) if row else None

    def role_by_uuid(self, uuid: str) -> Role | None:
        row = self.db.execute("SELECT * FROM role WHERE uuid = ?", (uuid,)).fetchone()
        return self._role(row) if row else None

    def save_role(self, role: Role) -> Role:
        ts = now_iso()
        if role.id is None:
            if not role.position:
                row = self.db.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM role").fetchone()
                role.position = row[0]
            cur = self.db.execute(
                "INSERT INTO role (uuid, name, emoji, color, avatar_path, position, language,"
                " visibility, signature, ai_style, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (role.uuid, role.name, role.emoji, role.color, role.avatar_path, role.position,
                 role.language, role.visibility, role.signature, role.ai_style, ts, ts),
            )
            role.id = cur.lastrowid
        else:
            self.db.execute(
                "UPDATE role SET name=?, emoji=?, color=?, avatar_path=?, position=?, language=?,"
                " visibility=?, signature=?, ai_style=?, updated_at=? WHERE id=?",
                (role.name, role.emoji, role.color, role.avatar_path, role.position, role.language,
                 role.visibility, role.signature, role.ai_style, ts, role.id),
            )
        return role

    def delete_role(self, role_id: int) -> None:
        self.db.execute("DELETE FROM role WHERE id = ?", (role_id,))

    def reorder_roles(self, ordered_ids: Iterable[int]) -> None:
        with self.transaction():
            for pos, rid in enumerate(ordered_ids):
                self.db.execute("UPDATE role SET position = ? WHERE id = ?", (pos, rid))

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------
    @staticmethod
    def _profile(row: sqlite3.Row) -> Profile:
        return Profile(
            id=row["id"], uuid=row["uuid"], platform=row["platform"], server=row["server"],
            remote_id=row["remote_id"], handle=row["handle"], display_name=row["display_name"],
            label=row["label"], avatar_url=row["avatar_url"], auth_method=row["auth_method"],
            status=ProfileStatus(row["status"]), status_detail=row["status_detail"],
            token_expires_at=row["token_expires_at"], limits_json=row["limits_json"],
            limits_fetched_at=row["limits_fetched_at"], options_json=row["options_json"],
        )

    def profiles(self) -> list[Profile]:
        rows = self.db.execute("SELECT * FROM profile ORDER BY platform, handle")
        return [self._profile(r) for r in rows]

    def profile(self, profile_id: int) -> Profile | None:
        row = self.db.execute("SELECT * FROM profile WHERE id = ?", (profile_id,)).fetchone()
        return self._profile(row) if row else None

    def find_profile(self, platform: str, server: str | None, remote_id: str) -> Profile | None:
        row = self.db.execute(
            "SELECT * FROM profile WHERE platform = ? AND IFNULL(server, '') = IFNULL(?, '')"
            " AND remote_id = ?", (platform, server, remote_id)).fetchone()
        return self._profile(row) if row else None

    def save_profile(self, p: Profile) -> Profile:
        ts = now_iso()
        if p.id is None:
            cur = self.db.execute(
                "INSERT INTO profile (uuid, platform, server, remote_id, handle, display_name, label,"
                " avatar_url, auth_method, status, status_detail, token_expires_at, limits_json,"
                " limits_fetched_at, options_json, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.uuid, p.platform, p.server, p.remote_id, p.handle, p.display_name, p.label,
                 p.avatar_url, p.auth_method, str(p.status), p.status_detail, p.token_expires_at,
                 p.limits_json, p.limits_fetched_at, p.options_json, ts, ts),
            )
            p.id = cur.lastrowid
        else:
            self.db.execute(
                "UPDATE profile SET server=?, remote_id=?, handle=?, display_name=?, label=?,"
                " avatar_url=?, auth_method=?, status=?, status_detail=?, token_expires_at=?,"
                " limits_json=?, limits_fetched_at=?, options_json=?, updated_at=? WHERE id=?",
                (p.server, p.remote_id, p.handle, p.display_name, p.label, p.avatar_url,
                 p.auth_method, str(p.status), p.status_detail, p.token_expires_at, p.limits_json,
                 p.limits_fetched_at, p.options_json, ts, p.id),
            )
        return p

    def delete_profile(self, profile_id: int) -> None:
        self.db.execute("DELETE FROM profile WHERE id = ?", (profile_id,))

    # ------------------------------------------------------------------
    # Rolle ↔ Profil
    # ------------------------------------------------------------------
    def role_profiles(self, role_id: int) -> list[RoleProfile]:
        rows = self.db.execute(
            "SELECT * FROM role_profile WHERE role_id = ? ORDER BY position, profile_id", (role_id,))
        return [RoleProfile(r["role_id"], r["profile_id"], bool(r["preselected"]), r["position"])
                for r in rows]

    def roles_of_profile(self, profile_id: int) -> list[int]:
        rows = self.db.execute("SELECT role_id FROM role_profile WHERE profile_id = ?", (profile_id,))
        return [r[0] for r in rows]

    def set_role_profile(self, role_id: int, profile_id: int, member: bool,
                         preselected: bool = True) -> None:
        if member:
            pos = self.db.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM role_profile WHERE role_id = ?",
                (role_id,)).fetchone()[0]
            self.db.execute(
                "INSERT INTO role_profile (role_id, profile_id, preselected, position)"
                " VALUES (?,?,?,?) ON CONFLICT(role_id, profile_id)"
                " DO UPDATE SET preselected = excluded.preselected",
                (role_id, profile_id, int(preselected), pos))
        else:
            self.db.execute("DELETE FROM role_profile WHERE role_id = ? AND profile_id = ?",
                            (role_id, profile_id))

    # ------------------------------------------------------------------
    # Beiträge
    # ------------------------------------------------------------------
    def save_post(self, post: Post) -> Post:
        """Speichert Beitrag samt Varianten, Medien und Zielen (ersetzend)."""
        post.updated_at = now_iso()
        with self.transaction():
            vals = (post.role_id, str(post.state), post.body, post.content_warning, post.language,
                    post.visibility, post.bluesky_label, int(post.use_signature), post.thread_mode,
                    post.scheduled_at, post.timezone, post.updated_at, post.published_at)
            if post.id is None:
                cur = self.db.execute(
                    "INSERT INTO post (role_id, state, body, content_warning, language, visibility,"
                    " bluesky_label, use_signature, thread_mode, scheduled_at, timezone, updated_at,"
                    " published_at, uuid, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    vals + (post.uuid, post.created_at))
                post.id = cur.lastrowid
            else:
                self.db.execute(
                    "UPDATE post SET role_id=?, state=?, body=?, content_warning=?, language=?,"
                    " visibility=?, bluesky_label=?, use_signature=?, thread_mode=?, scheduled_at=?,"
                    " timezone=?, updated_at=?, published_at=? WHERE id=?", vals + (post.id,))

            self.db.execute("DELETE FROM post_variant WHERE post_id = ?", (post.id,))
            for v in post.variants:
                cur = self.db.execute(
                    "INSERT INTO post_variant (post_id, platform, profile_id, body, content_warning,"
                    " base_hash) VALUES (?,?,?,?,?,?)",
                    (post.id, v.platform, v.profile_id, v.body, v.content_warning, v.base_hash))
                v.id = cur.lastrowid

            keep_media = [m.id for m in post.media if m.id is not None]
            self.db.execute(
                f"DELETE FROM media WHERE post_id = ? AND id NOT IN ({','.join('?' * len(keep_media))})",
                (post.id, *keep_media))
            for pos, m in enumerate(post.media):
                m.position = pos
                if m.id is None:
                    cur = self.db.execute(
                        "INSERT INTO media (post_id, position, path, sha256, mime, bytes, width,"
                        " height, duration_s, alt_text, focus_x, focus_y)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (post.id, pos, m.path, m.sha256, m.mime, m.bytes, m.width, m.height,
                         m.duration_s, m.alt_text, m.focus_x, m.focus_y))
                    m.id = cur.lastrowid
                else:
                    self.db.execute(
                        "UPDATE media SET position=?, alt_text=?, focus_x=?, focus_y=? WHERE id=?",
                        (pos, m.alt_text, m.focus_x, m.focus_y, m.id))

            keep_profiles = [t.profile_id for t in post.targets]
            self.db.execute(
                f"DELETE FROM post_target WHERE post_id = ? AND profile_id NOT IN"
                f" ({','.join('?' * len(keep_profiles))})", (post.id, *keep_profiles))
            for t in post.targets:
                self._save_target(post.id, t)
        return post

    def _save_target(self, post_id: int, t: Target) -> None:
        vals = (int(t.enabled), str(t.state), t.attempts, t.last_error, t.last_error_detail,
                t.remote_url, t.remote_scheduled_id, t.published_at)
        if t.id is None:
            row = self.db.execute(
                "SELECT id FROM post_target WHERE post_id = ? AND profile_id = ?",
                (post_id, t.profile_id)).fetchone()
            if row:
                t.id = row[0]
        if t.id is None:
            cur = self.db.execute(
                "INSERT INTO post_target (enabled, state, attempts, last_error, last_error_detail,"
                " remote_url, remote_scheduled_id, published_at, post_id, profile_id, idempotency_key)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)", vals + (post_id, t.profile_id, t.idempotency_key))
            t.id = cur.lastrowid
        else:
            self.db.execute(
                "UPDATE post_target SET enabled=?, state=?, attempts=?, last_error=?,"
                " last_error_detail=?, remote_url=?, remote_scheduled_id=?, published_at=?"
                " WHERE id=?", vals + (t.id,))
        for part in t.parts:
            self.db.execute(
                "INSERT INTO post_target_part (target_id, idx, remote_id, remote_cid, remote_url)"
                " VALUES (?,?,?,?,?) ON CONFLICT(target_id, idx) DO UPDATE SET"
                " remote_id=excluded.remote_id, remote_cid=excluded.remote_cid,"
                " remote_url=excluded.remote_url",
                (t.id, part.idx, part.remote_id, part.remote_cid, part.remote_url))

    def save_target(self, post_id: int, t: Target) -> None:
        with self.transaction():
            self._save_target(post_id, t)

    def update_post_state(self, post: Post) -> None:
        self.db.execute("UPDATE post SET state=?, published_at=?, updated_at=? WHERE id=?",
                        (str(post.state), post.published_at, now_iso(), post.id))

    def claim_post(self, post_id: int, lease_until: str, allowed: Iterable[PostState]) -> bool:
        """Beansprucht einen Beitrag atomar zum Senden. False = jemand anderes sendet."""
        states = [str(s) for s in allowed]
        cur = self.db.execute(
            f"UPDATE post SET state='sending', claimed_until=? WHERE id=? AND"
            f" (state IN ({','.join('?' * len(states))})"
            f"  OR (state='sending' AND claimed_until < ?))",
            (lease_until, post_id, *states, now_iso()))
        return cur.rowcount == 1

    def release_post(self, post_id: int) -> None:
        self.db.execute("UPDATE post SET claimed_until = NULL WHERE id = ?", (post_id,))

    def load_post(self, post_id: int) -> Post | None:
        row = self.db.execute("SELECT * FROM post WHERE id = ?", (post_id,)).fetchone()
        if not row:
            return None
        post = Post(
            id=row["id"], uuid=row["uuid"], role_id=row["role_id"], state=PostState(row["state"]),
            body=row["body"], content_warning=row["content_warning"], language=row["language"],
            visibility=row["visibility"], bluesky_label=row["bluesky_label"],
            use_signature=bool(row["use_signature"]), thread_mode=row["thread_mode"],
            scheduled_at=row["scheduled_at"], timezone=row["timezone"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            published_at=row["published_at"],
        )
        post.variants = [
            Variant(id=r["id"], platform=r["platform"], profile_id=r["profile_id"], body=r["body"],
                    content_warning=r["content_warning"], base_hash=r["base_hash"])
            for r in self.db.execute("SELECT * FROM post_variant WHERE post_id = ?", (post_id,))]
        post.media = [
            Media(id=r["id"], position=r["position"], path=r["path"], sha256=r["sha256"],
                  mime=r["mime"], bytes=r["bytes"], width=r["width"], height=r["height"],
                  duration_s=r["duration_s"], alt_text=r["alt_text"], focus_x=r["focus_x"],
                  focus_y=r["focus_y"])
            for r in self.db.execute("SELECT * FROM media WHERE post_id = ? ORDER BY position",
                                     (post_id,))]
        for r in self.db.execute("SELECT * FROM post_target WHERE post_id = ? ORDER BY id",
                                 (post_id,)):
            t = Target(
                id=r["id"], profile_id=r["profile_id"], enabled=bool(r["enabled"]),
                state=TargetState(r["state"]), idempotency_key=r["idempotency_key"],
                attempts=r["attempts"], last_error=r["last_error"],
                last_error_detail=r["last_error_detail"], remote_url=r["remote_url"],
                remote_scheduled_id=r["remote_scheduled_id"], published_at=r["published_at"])
            t.parts = [TargetPart(p["idx"], p["remote_id"], p["remote_cid"], p["remote_url"])
                       for p in self.db.execute(
                           "SELECT * FROM post_target_part WHERE target_id = ? ORDER BY idx", (t.id,))]
            post.targets.append(t)
        return post

    def post_ids(self, states: Iterable[PostState], order: str = "updated_at DESC",
                 limit: int = 500, search: str | None = None) -> list[int]:
        states = [str(s) for s in states]
        sql = (f"SELECT id FROM post WHERE deleted_at IS NULL AND"
               f" state IN ({','.join('?' * len(states))})")
        args: list[object] = list(states)
        if search:
            sql += " AND id IN (SELECT rowid FROM post_fts WHERE post_fts MATCH ?)"
            args.append(search)
        sql += f" ORDER BY {order} LIMIT ?"
        args.append(limit)
        return [r[0] for r in self.db.execute(sql, args)]

    def delete_post(self, post_id: int) -> None:
        self.db.execute("DELETE FROM post WHERE id = ?", (post_id,))

    def mark_post_deleted(self, post_id: int, deleted: bool) -> None:
        self.db.execute("UPDATE post SET deleted_at = ? WHERE id = ?",
                        (now_iso() if deleted else None, post_id))

    def purge_deleted_posts(self) -> None:
        self.db.execute("DELETE FROM post WHERE deleted_at IS NOT NULL")

    def purge_empty_drafts(self, older_than_iso: str) -> None:
        self.db.execute(
            "DELETE FROM post WHERE state = 'draft' AND trim(body) = '' AND updated_at < ?"
            " AND NOT EXISTS (SELECT 1 FROM media WHERE media.post_id = post.id)"
            " AND NOT EXISTS (SELECT 1 FROM post_variant v WHERE v.post_id = post.id"
            "                 AND trim(v.body) <> '')", (older_than_iso,))

    # ------------------------------------------------------------------
    # Upload-Cache
    # ------------------------------------------------------------------
    def media_upload(self, media_id: int, profile_id: int) -> str | None:
        row = self.db.execute(
            "SELECT remote_ref FROM media_upload WHERE media_id = ? AND profile_id = ?"
            " AND (expires_at IS NULL OR expires_at > ?)",
            (media_id, profile_id, now_iso())).fetchone()
        return row[0] if row else None

    def save_media_upload(self, media_id: int, profile_id: int, remote_ref: str,
                          expires_at: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO media_upload (media_id, profile_id, remote_ref, uploaded_at, expires_at)"
            " VALUES (?,?,?,?,?) ON CONFLICT(media_id, profile_id) DO UPDATE SET"
            " remote_ref=excluded.remote_ref, uploaded_at=excluded.uploaded_at,"
            " expires_at=excluded.expires_at",
            (media_id, profile_id, remote_ref, now_iso(), expires_at))


class _Tx:
    """Verschachtelbare Transaktion über SAVEPOINTs."""

    _depth: dict[int, int] = {}

    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db

    def __enter__(self) -> "_Tx":
        key = id(self.db)
        depth = self._depth.get(key, 0)
        self.name = f"sp{depth}"
        self.db.execute(f"SAVEPOINT {self.name}")
        self._depth[key] = depth + 1
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        key = id(self.db)
        self._depth[key] -= 1
        if exc_type is None:
            self.db.execute(f"RELEASE {self.name}")
        else:
            self.db.execute(f"ROLLBACK TO {self.name}")
            self.db.execute(f"RELEASE {self.name}")
