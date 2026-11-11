# SPDX-License-Identifier: GPL-3.0-or-later
"""Deck: je Profil einer Rolle eine Spalte mit der Home-Timeline.

Phase 1 des Lese-Modus (siehe docs/deck-columns.md): nur lesen, Mastodon,
Abfrage alle 60 Sekunden, solange das Deck sichtbar ist.
"""

from __future__ import annotations

import logging
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk, Pango

from .core.models import Profile, Role
from .feedview import FeedView
from .reader.base import HOME, MESSAGES, NOTIFICATIONS
from .widgets.avatars import AvatarCache
from .widgets.profile_chip import platform_badge

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

log = logging.getLogger(__name__)

COLUMN_WIDTH = 360
POLL_SECONDS = 60


FEED_TITLES = {HOME: _("Home"), NOTIFICATIONS: _("Notifications"), MESSAGES: _("Messages")}


class DeckColumn(Gtk.Box):
    """Eine Spalte für ein Profil mit den Reitern Home, Benachrichtigungen und Nachrichten."""

    def __init__(self, deck: DandelionDeck, profile: Profile) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, width_request=COLUMN_WIDTH)
        self.add_css_class("deck-column")
        self.deck = deck
        self.profile = profile
        self.views: dict[str, FeedView] = {}

        head = Gtk.Box(spacing=10, margin_top=10, margin_bottom=6, margin_start=12, margin_end=6)
        avatar = Adw.Avatar(size=32, text=profile.title, show_initials=True)
        deck.avatars.apply(avatar, profile.avatar_url)
        overlay = Gtk.Overlay(child=avatar, valign=Gtk.Align.CENTER)
        overlay.add_overlay(platform_badge(profile.platform))
        head.append(overlay)
        who = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        title = Gtk.Label(label=profile.title, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        title.add_css_class("heading")
        who.append(title)
        handle = Gtk.Label(label=profile.full_handle, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        handle.add_css_class("dim-label")
        handle.add_css_class("caption")
        who.append(handle)
        head.append(who)
        self.new_post_button = Gtk.Button(icon_name="document-edit-symbolic", valign=Gtk.Align.CENTER,
                                          tooltip_text=_("New Post as {name}").format(name=profile.title))
        self.new_post_button.add_css_class("flat")
        self.new_post_button.update_property([Gtk.AccessibleProperty.LABEL], [_("New Post")])
        self.new_post_button.connect("clicked", lambda *_a: self._new_post())
        head.append(self.new_post_button)
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER,
                                         tooltip_text=_("Refresh"))
        self.refresh_button.add_css_class("flat")
        self.refresh_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Refresh")])
        self.refresh_button.connect("clicked", lambda *_a: self.refresh(manual=True))
        head.append(self.refresh_button)
        self.append(head)

        self.stack = Adw.ViewStack(vexpand=True)
        feeds = deck.service.feeds(profile)
        for feed in feeds:
            view = FeedView(self, feed)
            self.views[feed] = view
            page = self.stack.add_titled(view, feed, FEED_TITLES[feed])
            page.set_name(feed)
        if len(feeds) > 1:
            switcher = Adw.InlineViewSwitcher(stack=self.stack, margin_start=12, margin_end=12,
                                              margin_bottom=6)
            switcher.set_display_mode(Adw.InlineViewSwitcherDisplayMode.LABELS)
            self.append(switcher)
        self.append(self.stack)
        self.update_badges()
        self.refresh(manual=True)

    def _new_post(self) -> None:
        from .quickpost import ComposeSheet
        ComposeSheet(self.deck.app, self.deck.win, self.profile, "new",
                     on_sent=lambda: self.refresh()).present(self.deck.win)

    def update_badges(self) -> None:
        for feed, view in self.views.items():
            if feed == HOME:
                continue
            page = self.stack.get_page(view)
            n = view.unread_count()
            page.set_badge_number(n)
            page.set_needs_attention(n > 0)

    def unread_total(self) -> int:
        return self.deck.service.unread_total(self.profile)

    def refresh(self, manual: bool = False) -> None:
        for view in self.views.values():
            view.refresh(manual=manual)


class DandelionDeck(Gtk.Box):
    __gtype_name__ = "DandelionDeck"

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.role: Role | None = None
        self.columns: list[DeckColumn] = []
        self._timer = 0

        self.columns_box = Gtk.Box()
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                           vscrollbar_policy=Gtk.PolicyType.NEVER,
                                           child=self.columns_box, vexpand=True, hexpand=True)
        self.empty = Adw.StatusPage(icon_name="mail-unread-symbolic",
                                    title=_("Nothing to Read Here"),
                                    description=_("Add a Mastodon profile to this role to see "
                                                  "its timeline."))
        self.empty_button = Gtk.Button(label=_("Roles and Profiles"), halign=Gtk.Align.CENTER)
        self.empty_button.add_css_class("pill")
        self.empty_button.add_css_class("suggested-action")
        self.empty_button.set_action_name("win.manage-roles")
        self.empty.set_child(self.empty_button)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.scroller, "columns")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self.service = app.reader
        self.avatars = AvatarCache(app.http)

    # -- Rolle --------------------------------------------------------------
    def set_role(self, role: Role | None) -> None:
        self.role = role
        self.reload()

    def reload(self) -> None:
        """Baut die Spalten der gewählten Rolle neu auf."""
        while (child := self.columns_box.get_first_child()) is not None:
            self.columns_box.remove(child)
        self.columns = []
        profiles: list[Profile] = []
        if self.role is not None:
            for rp in self.app.store.role_profiles(self.role.id):  # type: ignore[arg-type]
                p = self.app.store.profile(rp.profile_id)
                if p is not None and self.service.can_read(p):
                    profiles.append(p)
        for p in profiles:
            column = DeckColumn(self, p)
            if len(profiles) == 1:
                column.set_hexpand(True)
            self.columns.append(column)
            self.columns_box.append(column)
            if p is not profiles[-1]:
                self.columns_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.stack.set_visible_child_name("columns" if profiles else "empty")

    def unread_changed(self) -> None:
        """Ein Lesestand oder Zähler hat sich geändert: Rollenliste auffrischen."""
        if not getattr(self, "_badge_pending", False):
            self._badge_pending = True

            def run() -> bool:
                self._badge_pending = False
                self.win.update_read_badges()
                return GLib.SOURCE_REMOVE
            GLib.idle_add(run)

    def column_count(self) -> int:
        return len(self.columns)

    def refresh_all(self, manual: bool = True) -> None:
        for column in self.columns:
            column.refresh(manual=manual)

    # -- Abfrage ------------------------------------------------------------
    def _on_map(self, *_args: object) -> None:
        if not self._timer:
            self._timer = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self.refresh_all(manual=False)

    def _on_unmap(self, *_args: object) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _poll(self) -> bool:
        self.refresh_all(manual=False)
        return GLib.SOURCE_CONTINUE
