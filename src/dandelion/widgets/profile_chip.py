# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from gettext import gettext as _

from gi.repository import Adw, Gtk

from ..core.models import Profile, ProfileStatus
from .avatars import AvatarCache

STATUS_TEXT = {
    ProfileStatus.OK: _("signed in"),
    ProfileStatus.EXPIRING: _("login expires soon"),
    ProfileStatus.EXPIRED: _("signed out"),
    ProfileStatus.ERROR: _("connection error"),
}


def platform_badge(platform_id: str, size: int = 10) -> Gtk.Widget:
    """Stilisierter Plattform-Punkt in der Plattformfarbe (kein Markenlogo)."""
    dot = Gtk.Box(width_request=size, height_request=size, valign=Gtk.Align.END,
                  halign=Gtk.Align.END)
    dot.add_css_class("platform-dot")
    dot.add_css_class(f"platform-{platform_id}")
    return dot


class ProfileChip(Gtk.ToggleButton):
    """Auswahl eines Profils im Composer: Avatar, Plattform, Handle, Status."""

    def __init__(self, profile: Profile, platform_name: str, avatars: AvatarCache) -> None:
        super().__init__()
        self.profile = profile
        self.platform_name = platform_name
        self.add_css_class("profile-chip")

        box = Gtk.Box(spacing=6)
        overlay = Gtk.Overlay()
        self.avatar = Adw.Avatar(size=24, text=profile.title, show_initials=True)
        avatars.apply(self.avatar, profile.avatar_url)
        overlay.set_child(self.avatar)
        overlay.add_overlay(platform_badge(profile.platform))
        box.append(overlay)

        self.label = Gtk.Label(label=profile.label or profile.full_handle)
        box.append(self.label)

        if profile.status != ProfileStatus.OK:
            warn = Gtk.Image(icon_name="dialog-warning-symbolic")
            warn.add_css_class("warning" if profile.status == ProfileStatus.EXPIRING else "error")
            box.append(warn)
        self.set_child(box)
        self.connect("toggled", lambda *_: self._update_a11y())
        self._update_a11y()

    def set_compact(self, compact: bool) -> None:
        self.label.set_visible(not compact)

    def _update_a11y(self) -> None:
        state = _("selected") if self.get_active() else _("not selected")
        text = _("Profile {handle} on {platform}, {status}, {state}").format(
            handle=self.profile.full_handle, platform=self.platform_name,
            status=STATUS_TEXT[self.profile.status], state=state)
        self.update_property([Gtk.AccessibleProperty.LABEL], [text])
        self.set_tooltip_text(f"{self.profile.full_handle} · {self.platform_name}")
