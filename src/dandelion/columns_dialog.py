# SPDX-License-Identifier: GPL-3.0-or-later
"""Spalten einer Rolle einrichten: Reihenfolge, entfernen, Listen und Hashtags hinzufügen."""

from __future__ import annotations

import logging
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gtk

from .core.models import DeckColumnSpec, Profile, Role
from .platforms.base import PlatformError
from .reader.base import FeedSource
from .util import spawn

if TYPE_CHECKING:
    from .deck import DandelionDeck

log = logging.getLogger(__name__)


def _icon_button(icon: str, tip: str, callback, sensitive: bool = True) -> Gtk.Button:  # type: ignore[no-untyped-def]
    b = Gtk.Button(icon_name=icon, valign=Gtk.Align.CENTER, tooltip_text=tip, sensitive=sensitive)
    b.add_css_class("flat")
    b.update_property([Gtk.AccessibleProperty.LABEL], [tip])
    b.connect("clicked", lambda *_a: callback())
    return b


class ColumnsDialog(Adw.Dialog):
    __gtype_name__ = "DandelionColumnsDialog"

    def __init__(self, deck: DandelionDeck, role: Role) -> None:
        super().__init__(title=_("Columns"), content_width=520, content_height=680)
        self.deck, self.role = deck, role
        self.service = deck.service
        self.store = deck.app.store
        self.specs: list[DeckColumnSpec] = list(self.service.columns(role))
        self._rows: list[Adw.ActionRow] = []
        self._expanders: dict[int, tuple[Adw.ExpanderRow, list[Gtk.Widget]]] = {}

        page = Adw.PreferencesPage()
        self.group = Adw.PreferencesGroup(
            title=_("Columns in {role}").format(role=f"{role.emoji} {role.name}"),
            description=_("Left to right. Without any columns, every profile gets one."))
        page.add(self.group)
        self.add_group = Adw.PreferencesGroup(
            title=_("Add a Column"),
            description=_("Open a profile to see its lists, hashtags and bookmarks. "
                          "Hashtags in posts can be added directly."))
        page.add(self.add_group)

        header = Adw.HeaderBar()
        view = Adw.ToolbarView(content=page)
        view.add_top_bar(header)
        self.set_child(view)

        for rp in self.store.role_profiles(role.id):  # type: ignore[arg-type]
            profile = self.store.profile(rp.profile_id)
            if profile is not None and self.service.can_read(profile):
                self._add_profile(profile)
        self._render_columns()

    # -- Spalten ------------------------------------------------------------
    def _avatar(self, profile: Profile) -> Adw.Avatar:
        avatar = Adw.Avatar(size=32, text=profile.title, show_initials=True)
        self.deck.avatars.apply(avatar, profile.avatar_url)
        return avatar

    def _save(self) -> None:
        self.service.save_columns(self.role, self.specs)
        self.specs = list(self.service.columns(self.role))   # leer → Standardspalten
        self._render_columns()

    def _render_columns(self) -> None:
        for row in self._rows:
            self.group.remove(row)
        self._rows = []
        for i, spec in enumerate(self.specs):
            profile = self.store.profile(spec.profile_id)
            if profile is None:
                continue
            row = Adw.ActionRow(
                title=spec.title if spec.kind == "feed" else profile.title,
                subtitle=(profile.full_handle if spec.kind == "feed" else
                          f"{profile.full_handle} · " + _("Home, Notifications, Messages")))
            row.add_prefix(self._avatar(profile))
            row.add_suffix(_icon_button("go-up-symbolic", _("Move Left"),
                                        lambda i=i: self._move(i, -1), i > 0))
            row.add_suffix(_icon_button("go-down-symbolic", _("Move Right"),
                                        lambda i=i: self._move(i, 1), i < len(self.specs) - 1))
            row.add_suffix(_icon_button("user-trash-symbolic", _("Remove Column"),
                                        lambda i=i: self._remove(i)))
            self.group.add(row)
            self._rows.append(row)
        for profile_id, (expander, _rows) in self._expanders.items():
            self._refresh_expander_state(profile_id)

    def _move(self, i: int, delta: int) -> None:
        j = i + delta
        if 0 <= j < len(self.specs):
            self.specs[i], self.specs[j] = self.specs[j], self.specs[i]
            self._save()

    def _remove(self, i: int) -> None:
        del self.specs[i]
        self._save()

    def _has(self, profile: Profile, kind: str, feed: str) -> bool:
        return any(s.profile_id == profile.id and s.kind == kind and s.feed == feed
                   for s in self.specs)

    def _add(self, profile: Profile, kind: str, feed: str, title: str) -> None:
        if self._has(profile, kind, feed):
            return
        self.specs.append(DeckColumnSpec(self.role.id, profile.id, kind, feed, title))  # type: ignore[arg-type]
        self._save()

    # -- Hinzufügen ---------------------------------------------------------
    def _add_profile(self, profile: Profile) -> None:
        expander = Adw.ExpanderRow(title=profile.title, subtitle=profile.full_handle)
        expander.add_prefix(self._avatar(profile))
        self._expanders[profile.id] = (expander, [])        # type: ignore[index]
        loaded = {"done": False}

        def on_expanded(row: Adw.ExpanderRow, *_a: object) -> None:
            if row.get_expanded() and not loaded["done"]:
                loaded["done"] = True
                self._load_sources(profile)
        expander.connect("notify::expanded", on_expanded)
        self.add_group.add(expander)

    def _clear_expander(self, profile: Profile) -> None:
        expander, rows = self._expanders[profile.id]        # type: ignore[index]
        for row in rows:
            expander.remove(row)
        rows.clear()

    def _load_sources(self, profile: Profile) -> None:
        expander, rows = self._expanders[profile.id]        # type: ignore[index]
        loading = Adw.ActionRow(title=_("Loading…"))
        loading.add_prefix(Gtk.Spinner(spinning=True))
        expander.add_row(loading)
        rows.append(loading)

        async def run() -> None:
            sources: list[FeedSource] = []
            error = ""
            try:
                sources = await self.service.sources(profile)
            except PlatformError as e:
                error = e.message
            except Exception:
                log.exception("Quellen von %s nicht lesbar", profile.full_handle)
                error = _("Could not load the lists.")
            self._clear_expander(profile)
            if error:
                row = Adw.ActionRow(title=error)
                expander.add_row(row)
                rows.append(row)
                return
            self._sources = getattr(self, "_sources", {})
            self._sources[profile.id] = sources
            self._build_source_rows(profile)
        spawn(run())

    def _build_source_rows(self, profile: Profile) -> None:
        expander, rows = self._expanders[profile.id]        # type: ignore[index]
        self._clear_expander(profile)
        entries: list[tuple[str, str, str, str, str]] = [
            ("profile", "", profile.title, _("Profile column"),
             _("Home, Notifications and Messages"))]
        for s in getattr(self, "_sources", {}).get(profile.id, []):
            entries.append(("feed", s.feed, s.title, s.title, s.subtitle))
        for kind, feed, title, shown, subtitle in entries:
            row = Adw.ActionRow(title=shown, subtitle=subtitle)
            present = self._has(profile, kind, feed)
            button = _icon_button("object-select-symbolic" if present else "list-add-symbolic",
                                  _("Added") if present else _("Add Column"),
                                  lambda k=kind, f=feed, t=title: self._add(profile, k, f, t),
                                  not present)
            row.add_suffix(button)
            expander.add_row(row)
            rows.append(row)

    def _refresh_expander_state(self, profile_id: int) -> None:
        profile = self.store.profile(profile_id)
        if profile is not None and profile_id in getattr(self, "_sources", {}):
            self._build_source_rows(profile)
