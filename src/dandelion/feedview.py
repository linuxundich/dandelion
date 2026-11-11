# SPDX-License-Identifier: GPL-3.0-or-later
"""Eine Liste in einer Deck-Spalte: Home, Benachrichtigungen oder Nachrichten."""

from __future__ import annotations

import logging
from gettext import gettext as _
from gettext import ngettext
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk

from .core.models import Profile
from .platforms.base import PlatformError
from .reader.base import (
    MESSAGES,
    NOTIFICATIONS,
    POST_REASONS,
    FeedConversation,
    FeedItem,
    FeedPost,
    ReadScopeMissing,
)
from .util import spawn
from .widgets.feed_rows import conversation_row, notification_row, post_row

if TYPE_CHECKING:
    from .deck import DeckColumn

log = logging.getLogger(__name__)

FIRST_ROWS = 60
MORE_ROWS = 40
READ_AFTER_SECONDS = 2

EMPTY = {
    "home": (_("No Posts Yet"), _("Follow some accounts to fill this column.")),
    "notifications": (_("No Notifications"), _("Mentions, favourites, boosts and new followers "
                                                "appear here.")),
    "messages": (_("No Messages"), _("Direct conversations appear here.")),
}


class FeedView(Gtk.Box):
    def __init__(self, column: DeckColumn, feed: str) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.column = column
        self.feed = feed
        self.profile: Profile = column.profile
        self.service = column.deck.service
        self.items: list[FeedItem] = []
        self.shown = FIRST_ROWS
        self.pending = 0
        self.snapshot: str | None = None      # Lesestand beim Aufbau der Liste
        self.only_mentions = False
        self._busy = False
        self._exhausted = False
        self._read_timer = 0
        self._status_handler = 0

        if feed == NOTIFICATIONS:
            self.filter = Adw.ToggleGroup(homogeneous=True, margin_start=12, margin_end=12,
                                          margin_top=6, margin_bottom=6)
            self.filter.add(Adw.Toggle(name="all", label=_("All")))
            self.filter.add(Adw.Toggle(name="mentions", label=_("Mentions")))
            self.filter.connect("notify::active-name", self._on_filter)
            self.append(self.filter)

        self.new_button = Gtk.Button()
        for c in ("suggested-action", "pill"):
            self.new_button.add_css_class(c)
        self.new_button.set_halign(Gtk.Align.CENTER)
        self.new_button.set_margin_bottom(6)
        self.new_button.connect("clicked", self._show_pending)
        self.new_bar = Gtk.Revealer(child=self.new_button)
        self.append(self.new_bar)
        self.append(Gtk.Separator())

        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER,
                                         valign=Gtk.Align.CENTER, width_request=32,
                                         height_request=32), "loading")
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.listbox.add_css_class("feed-list")
        self.older_button = Gtk.Button(label=_("Show Older"), halign=Gtk.Align.CENTER,
                                       margin_top=12, margin_bottom=12)
        self.older_button.add_css_class("pill")
        self.older_button.connect("clicked", self._older)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        inner.append(self.listbox)
        inner.append(self.older_button)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, child=inner)
        self.scroller.get_vadjustment().connect("value-changed", lambda *_a: self._schedule_read())
        self.stack.add_named(self.scroller, "list")
        self.status = Adw.StatusPage()
        self.status.add_css_class("compact")
        self.status_button = Gtk.Button(halign=Gtk.Align.CENTER)
        self.status_button.add_css_class("pill")
        self.status.set_child(self.status_button)
        self.stack.add_named(self.status, "status")
        title, text = EMPTY[feed]
        self.empty = Adw.StatusPage(icon_name="mail-unread-symbolic", title=title, description=text)
        self.empty.add_css_class("compact")
        self.stack.add_named(self.empty, "empty")
        self.append(self.stack)

        self.connect("map", lambda *_a: self._schedule_read())
        self.connect("unmap", lambda *_a: self._stop_read_timer())

        cached = self.service.cached(self.profile, feed)
        if cached:
            self._set_items(cached)
        else:
            self.stack.set_visible_child_name("loading")

    # -- Anzeige ------------------------------------------------------------
    def visible_items(self) -> list[FeedItem]:
        if self.feed == NOTIFICATIONS and self.only_mentions:
            return [i for i in self.items
                    if isinstance(i, FeedPost) and i.reason in ("mention", "reply", "quote")]
        return self.items

    def _row(self, item: FeedItem) -> Gtk.Widget:
        avatars = self.column.deck.avatars
        if isinstance(item, FeedConversation):
            return conversation_row(item, avatars)
        unread = bool(self.snapshot and item.sort_ts > self.snapshot)
        if self.feed == NOTIFICATIONS and item.reason not in POST_REASONS:
            return notification_row(item, avatars, unread)
        return post_row(item, avatars, unread)

    def _render(self) -> None:
        while (row := self.listbox.get_first_child()) is not None:
            self.listbox.remove(row)
        items = self.visible_items()
        for item in items[: self.shown]:
            self.listbox.append(self._row(item))
        self.older_button.set_visible(not (self._exhausted and self.shown >= len(items)))
        self.stack.set_visible_child_name("list" if items else "empty")

    def _set_items(self, items: list[FeedItem]) -> None:
        self.items = items
        self.pending = 0
        self.new_bar.set_reveal_child(False)
        self.snapshot = self.service.marker(self.profile, self.feed)
        self._render()
        self.column.update_badges()
        self._schedule_read()

    def _on_filter(self, group: Adw.ToggleGroup, *_args: object) -> None:
        self.only_mentions = group.get_active_name() == "mentions"
        self.shown = FIRST_ROWS
        self._render()

    def _show_pending(self, *_args: object) -> None:
        self._set_items(self.service.cached(self.profile, self.feed))
        self.scroller.get_vadjustment().set_value(0)

    def _merge_new(self, items: list[FeedItem]) -> None:
        known = {i.id for i in self.items}
        fresh = [i for i in items if i.id not in known]
        at_top = self.scroller.get_vadjustment().get_value() < 8
        if not self.items or at_top:
            self._set_items(items)
            return
        self.pending = len(fresh)
        if fresh:
            self.new_button.set_label(
                ngettext("{n} new item", "{n} new items", len(fresh)).format(n=len(fresh)))
            self.new_bar.set_reveal_child(True)
        self.column.update_badges()

    def _older(self, *_args: object) -> None:
        if self.shown + MORE_ROWS <= len(self.visible_items()) or self._exhausted:
            self.shown += MORE_ROWS
            self._render()
            return

        async def run() -> None:
            before = len(self.items)
            try:
                items = await self.service.load_older(self.profile, self.feed)
            except PlatformError as e:
                self.column.deck.win.toast(e.message)
                return
            self._exhausted = len(items) == before
            self.items = items
            self.shown += MORE_ROWS
            self._render()

        spawn(run())

    # -- Lesestand ----------------------------------------------------------
    def unread_count(self) -> int:
        return self.service.unread(self.profile, self.feed)

    def _schedule_read(self) -> None:
        """Markiert die Liste als gelesen, wenn sie oben steht und einige Sekunden sichtbar war."""
        if self.feed == MESSAGES or self._read_timer or not self.get_mapped():
            return
        if self.unread_count() == 0:
            return
        self._read_timer = GLib.timeout_add_seconds(READ_AFTER_SECONDS, self._read_tick)

    def _read_tick(self) -> bool:
        """Läuft, solange die Liste sichtbar ist und Ungelesenes hat; markiert, sobald sie
        oben steht und das Fenster im Vordergrund ist."""
        if not self.get_mapped():
            self._read_timer = 0
            return GLib.SOURCE_REMOVE
        root = self.get_root()
        at_top = self.scroller.get_vadjustment().get_value() < 8
        if not at_top or (root is not None and not root.is_active()):
            return GLib.SOURCE_CONTINUE
        self._read_timer = 0
        spawn(self._mark_read())
        return GLib.SOURCE_REMOVE

    async def _mark_read(self) -> None:
        await self.service.mark_read(self.profile, self.feed)
        self.column.update_badges()
        self.column.deck.unread_changed()

    def _stop_read_timer(self) -> None:
        if self._read_timer:
            GLib.source_remove(self._read_timer)
            self._read_timer = 0

    # -- Laden --------------------------------------------------------------
    def _show_status(self, icon: str, title: str, text: str, button: str | None,
                     callback) -> None:  # type: ignore[no-untyped-def]
        self.status.set_icon_name(icon)
        self.status.set_title(title)
        self.status.set_description(text)
        if self._status_handler:
            self.status_button.disconnect(self._status_handler)
            self._status_handler = 0
        self.status_button.set_visible(bool(button))
        if button:
            self.status_button.set_label(button)
            self._status_handler = self.status_button.connect("clicked", lambda *_a: callback())
        self.stack.set_visible_child_name("status")

    def refresh(self, manual: bool = False) -> None:
        if self._busy:
            return
        self._busy = True

        async def run() -> None:
            try:
                items = await self.service.refresh(self.profile, self.feed)
            except ReadScopeMissing:
                if not self.items:
                    self._show_status(
                        "dialog-password-symbolic", _("Allow Reading"),
                        _("{handle} was signed in before Dandelion could read timelines. "
                          "Sign in again to allow reading.").format(handle=self.profile.full_handle),
                        _("Sign In Again"), lambda: self.column.deck.win.relogin(self.profile))
            except PlatformError as e:
                if not self.items:
                    if e.auth:
                        self._show_status("dialog-password-symbolic", _("Sign In Again"),
                                          e.message, _("Sign In Again"),
                                          lambda: self.column.deck.win.relogin(self.profile))
                    else:
                        self._show_status("network-error-symbolic", _("Could Not Load Posts"),
                                          e.message, _("Try Again"),
                                          lambda: self.refresh(manual=True))
                elif manual:
                    self.column.deck.win.toast(e.message)
            except Exception:                                  # Antwort mit unerwartetem Aufbau
                log.exception("Liste %s von %s nicht lesbar", self.feed, self.profile.full_handle)
                if not self.items:
                    self._show_status("dialog-error-symbolic", _("Could Not Read the Answer"),
                                      _("The server sent data Dandelion does not understand."),
                                      _("Try Again"), lambda: self.refresh(manual=True))
            else:
                if manual:
                    self._set_items(items)
                else:
                    self._merge_new(items)
            finally:
                self._busy = False
                self.column.deck.unread_changed()

        spawn(run())
