# SPDX-License-Identifier: GPL-3.0-or-later
"""Sendet einen Beitrag parallel an alle aktiven Profile."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from gettext import gettext as _

from ..platforms import Registry
from ..platforms.base import PlatformError
from .compose import composition_for
from .models import Post, PostState, Target, TargetPart, TargetState, now_iso
from .store import Store

log = logging.getLogger(__name__)

#: Gültigkeit hochgeladener, noch nicht verwendeter Medien je Plattform
UPLOAD_TTL = {"mastodon": timedelta(hours=6), "bluesky": timedelta(minutes=30)}
SENDABLE = (PostState.DRAFT, PostState.SCHEDULED, PostState.MISSED, PostState.PARTIAL,
            PostState.FAILED, PostState.PAUSED)
RETRY_DELAYS = (3.0,)

UpdateCallback = Callable[[Post, Target, str], None]


class AlreadySending(Exception):
    pass


def derive_state(post: Post) -> PostState:
    active = [t for t in post.targets if t.enabled]
    done = [t for t in active if t.state == TargetState.PUBLISHED]
    if active and len(done) == len(active):
        return PostState.PUBLISHED
    if done:
        return PostState.PARTIAL
    return PostState.FAILED


class Publisher:
    def __init__(self, store: Store, registry: Registry) -> None:
        self.store = store
        self.registry = registry

    async def send(self, post_id: int, *, only_profiles: set[int] | None = None,
                   on_update: UpdateCallback | None = None) -> Post:
        lease = (datetime.now(UTC) + timedelta(minutes=10)).isoformat(timespec="seconds")
        if not self.store.claim_post(post_id, lease, SENDABLE):
            raise AlreadySending()
        post = self.store.load_post(post_id)
        assert post is not None
        role = self.store.role(post.role_id) if post.role_id else None
        try:
            jobs = []
            for t in post.targets:
                if not t.enabled or t.state == TargetState.PUBLISHED:
                    continue
                if only_profiles is not None and t.profile_id not in only_profiles:
                    continue
                jobs.append(self._send_target(post, role, t, on_update))
            await asyncio.gather(*jobs)
            post.state = derive_state(post)
            if post.state in (PostState.PUBLISHED, PostState.PARTIAL) and not post.published_at:
                post.published_at = now_iso()
            self.store.update_post_state(post)
        finally:
            self.store.release_post(post_id)
            current = self.store.load_post(post_id)
            if current and current.state == PostState.SENDING:
                # Absturz oder Abbruch mittendrin: Zustand aus den Zielen ableiten
                current.state = derive_state(current)
                self.store.update_post_state(current)
        return post

    async def _send_target(self, post: Post, role, t: Target,  # type: ignore[no-untyped-def]
                           on_update: UpdateCallback | None) -> None:
        def notify(stage: str) -> None:
            if on_update:
                on_update(post, t, stage)

        profile = self.store.profile(t.profile_id)
        if profile is None or profile.platform not in self.registry:
            t.state = TargetState.FAILED
            t.last_error = _("The profile no longer exists.")
            self.store.save_target(post.id, t)  # type: ignore[arg-type]
            notify("failed")
            return
        platform = self.registry.get(profile.platform)
        comp = composition_for(post, profile, role)
        t.state = TargetState.SENDING
        t.attempts += 1
        t.last_error = t.last_error_detail = None
        self.store.save_target(post.id, t)  # type: ignore[arg-type]
        notify("start")

        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                refs: list[str] = []
                for i, m in enumerate(comp.media):
                    notify(f"upload:{i + 1}:{len(comp.media)}")
                    cached = self.store.media_upload(m.id, profile.id) if m.id else None  # type: ignore[arg-type]
                    if cached and json.loads(cached).get("_alt") == m.alt_text:
                        refs.append(cached)
                        continue
                    ref = await platform.upload_media(profile, m)
                    ref = json.dumps({**json.loads(ref), "_alt": m.alt_text})
                    if m.id:
                        ttl = UPLOAD_TTL.get(profile.platform, timedelta(minutes=30))
                        self.store.save_media_upload(
                            m.id, profile.id, ref,  # type: ignore[arg-type]
                            (datetime.now(UTC) + ttl).isoformat(timespec="seconds"))
                    refs.append(ref)
                clean = [json.dumps({k: v for k, v in json.loads(r).items() if k != "_alt"})
                         for r in refs]
                notify("posting")
                part: TargetPart = await platform.post(
                    profile, comp, clean, reply_to=None, root=None,
                    idempotency_key=t.idempotency_key)
                t.parts = [part]
                t.remote_url = part.remote_url
                t.state = TargetState.PUBLISHED
                t.published_at = now_iso()
                self.store.save_target(post.id, t)  # type: ignore[arg-type]
                notify("published")
                return
            except PlatformError as e:
                log.info("Senden an %s fehlgeschlagen: %s (%s)", profile.platform, e.message,
                         e.detail)
                if e.retryable and attempt < len(RETRY_DELAYS):
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                t.state = TargetState.FAILED
                t.last_error = e.message
                t.last_error_detail = e.detail or None
            except Exception as e:  # unerwartet: nicht abstürzen, sondern melden
                log.exception("Unerwarteter Fehler beim Senden an %s", profile.platform)
                t.state = TargetState.FAILED
                t.last_error = _("An unexpected error occurred.")
                t.last_error_detail = f"{type(e).__name__}: {e}"
            break
        self.store.save_target(post.id, t)  # type: ignore[arg-type]
        notify("failed")

    async def delete_remote(self, post_id: int, profile_id: int) -> None:
        post = self.store.load_post(post_id)
        assert post is not None
        target = next(t for t in post.targets if t.profile_id == profile_id)
        profile = self.store.profile(profile_id)
        assert profile is not None
        platform = self.registry.get(profile.platform)
        for part in reversed(target.parts):
            await platform.delete(profile, part)
        target.state = TargetState.DELETED
        self.store.save_target(post_id, target)
