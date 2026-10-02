# SPDX-License-Identifier: GPL-3.0-or-later
"""Serverseitiges Planen (Mastodon).

Für Profile mit der Option „Auf dem Server planen“ geht ein geplanter
Beitrag schon beim Planen an den Server. Er erscheint dann auch, wenn der
Rechner aus ist. Nach jeder Änderung gleicht `sync_post()` ab: Inhalt oder
Zeit geändert → neu anlegen, pausiert/gelöscht/kein Termin → beim Server
zurückziehen. Threads lassen sich nicht serverseitig planen (die Antworten
brauchen die ID des vorherigen Beitrags); sie laufen lokal.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta

from ..platforms import Registry
from ..platforms.base import PlatformError
from .compose import composition_for, thread_parts
from .models import PostState, Profile, Target, TargetState
from .publisher import Publisher
from .store import Store

log = logging.getLogger(__name__)

#: Mastodon nimmt geplante Beiträge erst ab fünf Minuten Vorlauf an
MIN_LEAD = timedelta(minutes=5, seconds=30)


def server_scheduling(profile: Profile) -> bool:
    if profile.platform != "mastodon" or not profile.options_json:
        return False
    try:
        return bool(json.loads(profile.options_json).get("server_scheduling"))
    except ValueError:
        return False


def set_server_scheduling(profile: Profile, enabled: bool) -> None:
    try:
        options = json.loads(profile.options_json) if profile.options_json else {}
    except ValueError:
        options = {}
    options["server_scheduling"] = enabled
    profile.options_json = json.dumps(options)


def _fingerprint(comp, at: str) -> str:  # type: ignore[no-untyped-def]
    raw = json.dumps([comp.text, comp.content_warning, comp.visibility, comp.language, at,
                      [(m.sha256, m.alt_text) for m in comp.media]])
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


class RemoteScheduler:
    def __init__(self, store: Store, registry: Registry, publisher: Publisher) -> None:
        self.store = store
        self.registry = registry
        self.publisher = publisher

    async def sync_post(self, post_id: int, *, deleted: bool = False,
                        now: datetime | None = None) -> list[str]:
        """Gleicht einen Beitrag mit dem Server ab. Liefert verständliche Fehler."""
        post = self.store.load_post(post_id)
        if post is None:
            return []
        now = now or datetime.now(UTC)
        role = self.store.role(post.role_id) if post.role_id else None
        errors: list[str] = []
        for t in post.targets:
            profile = self.store.profile(t.profile_id)
            if profile is None or profile.platform not in self.registry:
                continue
            platform = self.registry.get(profile.platform)
            if not hasattr(platform, "schedule_remote"):
                continue
            info = json.loads(t.remote_scheduled_id) if t.remote_scheduled_id else None
            comp = composition_for(post, profile, role)
            single = len(thread_parts(post, comp, platform, platform.limits_for(profile))) == 1
            want = (not deleted and t.enabled and server_scheduling(profile) and single
                    and post.state == PostState.SCHEDULED and post.scheduled_at is not None
                    and datetime.fromisoformat(post.scheduled_at) - now >= MIN_LEAD)
            due = post.scheduled_at is not None and \
                datetime.fromisoformat(post.scheduled_at) <= now
            if t.state == TargetState.SCHEDULED_REMOTE and due:
                # Der Server hat ihn schon veröffentlicht: nicht zurückziehen, eintragen
                await self.publisher._resolve_remote(post, profile, platform, t, lambda _s: None)
                continue
            try:
                if want:
                    fp = _fingerprint(comp, post.scheduled_at)  # type: ignore[arg-type]
                    if info and info.get("hash") == fp and t.state == TargetState.SCHEDULED_REMOTE:
                        continue
                    if info:
                        await platform.cancel_remote(profile, info["id"])
                    refs = await self.publisher.upload(platform, profile, comp)
                    sid = await platform.schedule_remote(
                        profile, comp, refs, post.scheduled_at,  # type: ignore[arg-type]
                        f"{t.idempotency_key}-sched-{fp}")
                    t.remote_scheduled_id = json.dumps({"id": sid, "hash": fp})
                    t.state = TargetState.SCHEDULED_REMOTE
                elif info or t.state == TargetState.SCHEDULED_REMOTE:
                    if info:
                        await platform.cancel_remote(profile, info["id"])
                    t.remote_scheduled_id = None
                    t.state = TargetState.PENDING
                else:
                    continue
            except PlatformError as e:
                log.info("Serverseitiges Planen für %s: %s", profile.full_handle, e.message)
                errors.append(f"{profile.full_handle}: {e.message}")
                # Lokal weiterplanen, damit der Beitrag trotzdem erscheint
                if t.state == TargetState.SCHEDULED_REMOTE and not want:
                    continue
                t.state = TargetState.PENDING
                t.remote_scheduled_id = None
            self.store.save_target(post.id, t)  # type: ignore[arg-type]
        return errors

    async def sync_all(self) -> list[str]:
        errors: list[str] = []
        for post_id, deleted in self.store.remote_candidates():
            errors += await self.sync_post(post_id, deleted=deleted)
        return errors


def remote_targets(targets: list[Target]) -> int:
    return sum(1 for t in targets if t.state == TargetState.SCHEDULED_REMOTE)
