# SPDX-License-Identifier: GPL-3.0-or-later
"""Prüfung eines Beitrags vor dem Senden, pro Profil."""

from __future__ import annotations

from dataclasses import dataclass, field
from gettext import gettext as _
from gettext import ngettext

from ..platforms import Registry
from ..platforms.base import Count, Issue, Platform, PlatformLimits
from dataclasses import replace

from .compose import base_text, composition_for, thread_parts
from .graphemes import count_graphemes
from .models import Post, Profile, ProfileStatus, Role


@dataclass
class TargetReport:
    profile: Profile
    platform: Platform
    limits: PlatformLimits
    count: Count
    issues: list[Issue] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]


@dataclass
class Report:
    general: list[Issue] = field(default_factory=list)
    targets: list[TargetReport] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.general if i.severity == "error"] + \
            [i for t in self.targets for i in t.errors]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.general if i.severity == "warning"] + \
            [i for t in self.targets for i in t.issues if i.severity == "warning"]

    @property
    def can_send(self) -> bool:
        return not self.errors

    @property
    def issue_count(self) -> int:
        return len(self.general) + sum(len(t.issues) for t in self.targets)


def _mb(n: int) -> str:
    return f"{n / 1_000_000:.0f} MB" if n >= 1_000_000 else f"{n / 1000:.0f} kB"


def validate_target(post: Post, profile: Profile, role: Role | None, platform: Platform,
                    require_alt_everywhere: bool) -> TargetReport:
    limits = platform.limits_for(profile)
    comp = composition_for(post, profile, role)
    parts = thread_parts(post, comp, platform, limits)
    if len(parts) > 1:
        # Im Thread zählt der längste Teil
        counts = [platform.count(replace(comp, text=p, media=[]), limits) for p in parts]
        count = max(counts, key=lambda c: c.used)
    else:
        count = platform.count(comp, limits)
    rep = TargetReport(profile, platform, limits, count, parts=parts)
    add = rep.issues.append

    if profile.status in (ProfileStatus.EXPIRED, ProfileStatus.ERROR):
        add(Issue("error", "auth", _("Not signed in. Please sign in again in the preferences.")))

    # Die Signatur allein ist kein Inhalt
    if not base_text(post, profile).strip() and not comp.media:
        add(Issue("error", "empty", _("The post is empty.")))
    if count.used > count.limit:
        over = count.used - count.limit
        add(Issue("error", "too_long", ngettext(
            "The text is {n} character too long.", "The text is {n} characters too long.",
            over).format(n=over)))
    elif count.bytes_limit is not None and (count.bytes_used or 0) > count.bytes_limit:
        add(Issue("error", "too_many_bytes", _("The text uses too many bytes (emoji and special "
                                               "characters count more).")))

    cost = platform.cost_notice(comp)
    if cost:
        add(Issue("warning", "cost", cost))

    images = [m for m in comp.media if m.is_image]
    videos = [m for m in comp.media if m.is_video]
    if len(images) > limits.max_images:
        add(Issue("error", "too_many_images", ngettext(
            "At most {n} image is allowed.", "At most {n} images are allowed.",
            limits.max_images).format(n=limits.max_images)))
    if videos and limits.max_videos == 0 or (videos and limits.max_video_bytes == 0):
        add(Issue("error", "video_unsupported",
                  _("Videos are not supported for {platform} yet.").format(platform=platform.name)))
    elif len(videos) > limits.max_videos:
        add(Issue("error", "too_many_videos", ngettext(
            "At most {n} video is allowed.", "At most {n} videos are allowed.",
            limits.max_videos).format(n=limits.max_videos)))
    if images and videos and not limits.allow_mixed_media:
        add(Issue("error", "mixed_media", _("Images and videos cannot be combined.")))

    for idx, m in enumerate(comp.media):
        allowed = limits.image_mime_types if m.is_image else limits.video_mime_types
        if allowed and m.mime not in allowed and not (m.is_image and limits.max_image_bytes is None):
            add(Issue("error", "mime", _("The file format of media {n} is not supported.").format(
                n=idx + 1), idx))
        max_bytes = limits.max_image_bytes if m.is_image else limits.max_video_bytes
        if max_bytes and m.bytes > max_bytes:
            add(Issue("error", "file_too_large", _("Media {n} is larger than {size}.").format(
                n=idx + 1, size=_mb(max_bytes)), idx))
        alt = m.alt_text.strip()
        if not alt:
            if limits.alt_text_required or require_alt_everywhere:
                add(Issue("error", "missing_alt", _("Media {n} has no alt text.").format(
                    n=idx + 1), idx))
            else:
                add(Issue("warning", "missing_alt", _("Media {n} has no alt text.").format(
                    n=idx + 1), idx))
        elif limits.alt_text_max and count_graphemes(alt) > limits.alt_text_max:
            add(Issue("error", "alt_too_long", _(
                "The alt text of media {n} is longer than {max} characters.").format(
                    n=idx + 1, max=limits.alt_text_max), idx))
    return rep


def validate(post: Post, role: Role | None, profiles: list[Profile], registry: Registry,
             require_alt_everywhere: bool = False) -> Report:
    report = Report()
    enabled = {t.profile_id for t in post.targets if t.enabled}
    selected = [p for p in profiles if p.id in enabled and p.platform in registry]
    if not selected:
        report.general.append(Issue("error", "no_profiles", _("Select at least one profile.")))
    for profile in selected:
        report.targets.append(validate_target(post, profile, role, registry.get(profile.platform),
                                              require_alt_everywhere))
    return report
