# SPDX-License-Identifier: GPL-3.0-or-later
"""Datenklassen für Rollen, Profile, Beiträge und Ziele."""

from __future__ import annotations

import uuid as _uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_uuid() -> str:
    return str(_uuid.uuid4())


class ProfileStatus(StrEnum):
    OK = "ok"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    ERROR = "error"


class PostState(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PAUSED = "paused"
    SENDING = "sending"
    PUBLISHED = "published"
    PARTIAL = "partial"
    FAILED = "failed"
    MISSED = "missed"


class TargetState(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    PUBLISHED = "published"
    FAILED = "failed"
    DELETED = "deleted"
    SCHEDULED_REMOTE = "scheduled_remote"


# Farbnamen der GNOME-Palette, passend zu den Akzentfarben von libadwaita
ROLE_COLORS = ("blue", "teal", "green", "yellow", "orange", "red", "pink", "purple", "slate")


@dataclass
class Role:
    name: str
    emoji: str = "💬"
    color: str = "blue"
    position: int = 0
    language: str | None = None
    visibility: str | None = None
    signature: str = ""
    ai_style: str = ""
    avatar_path: str | None = None
    #: Feste Zeitslots: [[Wochentag 0=Montag, "HH:MM"], …] in der lokalen Zeitzone
    slots: list[list[object]] = field(default_factory=list)
    id: int | None = None
    uuid: str = field(default_factory=new_uuid)


@dataclass
class Profile:
    platform: str
    remote_id: str
    handle: str
    auth_method: str
    server: str | None = None
    display_name: str = ""
    label: str = ""
    avatar_url: str | None = None
    status: ProfileStatus = ProfileStatus.OK
    status_detail: str = ""
    token_expires_at: str | None = None
    limits_json: str | None = None
    limits_fetched_at: str | None = None
    options_json: str | None = None
    id: int | None = None
    uuid: str = field(default_factory=new_uuid)

    @property
    def title(self) -> str:
        return self.label or self.display_name or self.handle

    @property
    def full_handle(self) -> str:
        if self.platform == "mastodon" and self.server:
            return f"@{self.handle}@{self.server}"
        if self.platform in ("linkedin", "facebook"):
            return self.handle          # Name bzw. Seitenname, kein @-Handle
        return f"@{self.handle}"


@dataclass
class RoleProfile:
    role_id: int
    profile_id: int
    preselected: bool = True
    position: int = 0


@dataclass
class Variant:
    platform: str
    body: str
    profile_id: int | None = None
    content_warning: str | None = None
    base_hash: str | None = None
    id: int | None = None


@dataclass
class Media:
    path: str
    sha256: str
    mime: str
    bytes: int
    position: int = 0
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    alt_text: str = ""
    focus_x: float | None = None
    focus_y: float | None = None
    id: int | None = None

    @property
    def is_image(self) -> bool:
        return self.mime.startswith("image/")

    @property
    def is_video(self) -> bool:
        return self.mime.startswith("video/")


@dataclass
class TargetPart:
    idx: int
    remote_id: str | None = None
    remote_cid: str | None = None
    remote_url: str | None = None


@dataclass
class Target:
    profile_id: int
    enabled: bool = True
    state: TargetState = TargetState.PENDING
    idempotency_key: str = field(default_factory=new_uuid)
    attempts: int = 0
    last_error: str | None = None
    last_error_detail: str | None = None
    remote_url: str | None = None
    remote_scheduled_id: str | None = None
    published_at: str | None = None
    parts: list[TargetPart] = field(default_factory=list)
    id: int | None = None


@dataclass
class Post:
    role_id: int | None = None
    state: PostState = PostState.DRAFT
    body: str = ""
    content_warning: str = ""
    language: str | None = None
    visibility: str | None = None
    bluesky_label: str | None = None
    use_signature: bool = True
    thread_mode: str = "off"
    scheduled_at: str | None = None
    timezone: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    published_at: str | None = None
    variants: list[Variant] = field(default_factory=list)
    media: list[Media] = field(default_factory=list)
    targets: list[Target] = field(default_factory=list)
    id: int | None = None
    uuid: str = field(default_factory=new_uuid)

    def variant_for(self, platform: str, profile_id: int | None = None) -> Variant | None:
        if profile_id is not None:
            for v in self.variants:
                if v.platform == platform and v.profile_id == profile_id:
                    return v
        for v in self.variants:
            if v.platform == platform and v.profile_id is None:
                return v
        return None

    def is_empty(self) -> bool:
        return not self.body.strip() and not self.media and not any(v.body.strip() for v in self.variants)
