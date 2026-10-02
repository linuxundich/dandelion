# SPDX-License-Identifier: GPL-3.0-or-later
"""Setzt den Inhalt für ein einzelnes Profil zusammen."""

from __future__ import annotations

import hashlib

from ..platforms.base import Composition
from .models import Post, Profile, Role


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def apply_signature(text: str, signature: str) -> str:
    sig = signature.strip()
    if not sig or sig in text:
        return text
    body = text.rstrip()
    return f"{body}\n\n{sig}" if body else sig


def base_text(post: Post, profile: Profile) -> str:
    """Profil-Variante vor Plattform-Variante vor Haupttext."""
    variant = post.variant_for(profile.platform, profile.id)
    return variant.body if variant else post.body


def composition_for(post: Post, profile: Profile, role: Role | None) -> Composition:
    variant = post.variant_for(profile.platform, profile.id)
    text = variant.body if variant else post.body
    if post.use_signature and role and role.signature:
        text = apply_signature(text, role.signature)
    cw = variant.content_warning if variant and variant.content_warning is not None \
        else post.content_warning
    return Composition(
        text=text,
        content_warning=cw.strip() if cw else "",
        language=post.language or (role.language if role else None),
        visibility=post.visibility or (role.visibility if role else None),
        content_label=post.bluesky_label,
        media=list(post.media),
    )


def thread_parts(post: Post, comp: Composition, platform, limits) -> list[str]:  # type: ignore[no-untyped-def]
    """Teile des Beitrags für diese Plattform (ein Teil ohne Thread-Modus)."""
    from dataclasses import replace

    from .splitting import THREAD_OFF, split_thread
    if post.thread_mode == THREAD_OFF or not limits.supports_threads:
        return [comp.text]

    def count(text: str) -> int:
        c = platform.count(replace(comp, text=text, media=[]), limits)
        if c.bytes_limit and (c.bytes_used or 0) > c.bytes_limit:
            return limits.max_chars + 1
        return c.used

    return split_thread(comp.text, count, limits.max_chars, post.thread_mode)
