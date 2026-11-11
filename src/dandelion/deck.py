# SPDX-License-Identifier: GPL-3.0-or-later
"""Deck: die Spalten einer Rolle (siehe docs/deck-columns.md).

Eine Profilspalte zeigt Home, Benachrichtigungen und Nachrichten eines Profils, eine
Listenspalte genau eine Liste (Liste, Hashtag, Lesezeichen, Feed). Mastodon hält
eine Live-Verbindung offen, alles andere wird alle 60 Sekunden abgefragt.
"""

from __future__ import annotations

import logging
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, GLib, GObject, Gtk, Pango

from .core.models import DeckColumnSpec, Profile, Role
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
    """Eine Spalte: Profilspalte mit Reitern oder eine einzelne Liste."""

    def __init__(self, deck: DandelionDeck, profile: Profile, spec: DeckColumnSpec) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, width_request=COLUMN_WIDTH)
        self.add_css_class("deck-column")
        self.deck = deck
        self.profile = profile
        self.spec = spec
        self.views: dict[str, FeedView] = {}
        single = spec.kind == "feed"

        head = Gtk.Box(spacing=10, margin_top=10, margin_bottom=6, margin_start=12, margin_end=6)
        avatar = Adw.Avatar(size=32, text=profile.title, show_initials=True)
        deck.avatars.apply(avatar, profile.avatar_url)
        overlay = Gtk.Overlay(child=avatar, valign=Gtk.Align.CENTER)
        overlay.add_overlay(platform_badge(profile.platform))
        head.append(overlay)
        who = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        title = Gtk.Label(label=spec.title if single else profile.title, xalign=0,
                          ellipsize=Pango.EllipsizeMode.END)
        title.add_css_class("heading")
        who.append(title)
        handle = Gtk.Label(label=profile.full_handle, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        handle.add_css_class("dim-label")
        handle.add_css_class("caption")
        who.append(handle)
        head.append(who)
        self.new_post_button = Gtk.Button(
            icon_name="document-edit-symbolic", valign=Gtk.Align.CENTER,
            tooltip_text=_("New Post as {name}").format(name=profile.title))
        self.new_post_button.add_css_class("flat")
        self.new_post_button.update_property([Gtk.AccessibleProperty.LABEL], [_("New Post")])
        self.new_post_button.connect("clicked", lambda *_a: self.new_post())
        head.append(self.new_post_button)
        self.refresh_button = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER,
                                         tooltip_text=_("Refresh"))
        self.refresh_button.add_css_class("flat")
        self.refresh_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Refresh")])
        self.refresh_button.connect("clicked", lambda *_a: self.refresh(manual=True))
        head.append(self.refresh_button)
        if single:
            close = Gtk.Button(icon_name="window-close-symbolic", valign=Gtk.Align.CENTER,
                               tooltip_text=_("Remove Column"))
            close.add_css_class("flat")
            close.update_property([Gtk.AccessibleProperty.LABEL], [_("Remove Column")])
            close.connect("clicked", lambda *_a: deck.remove_column(spec))
            head.append(close)
        self.append(head)

        self.stack = Adw.ViewStack(vexpand=True)
        feeds = (spec.feed,) if single else deck.service.feeds(profile)
        for feed in feeds:
            view = FeedView(self, feed)
            self.views[feed] = view
            page = self.stack.add_titled(view, feed, FEED_TITLES.get(feed, spec.title))
            page.set_name(feed)
        if len(feeds) > 1:
            switcher = Adw.InlineViewSwitcher(stack=self.stack, margin_start=12, margin_end=12,
                                              margin_bottom=6)
            switcher.set_display_mode(Adw.InlineViewSwitcherDisplayMode.LABELS)
            self.append(switcher)
        self.append(self.stack)
        self.update_badges()
        self.refresh(manual=True)

    def new_post(self) -> None:
        from .quickpost import ComposeSheet
        ComposeSheet(self.deck.app, self.deck.win, self.profile, "new",
                     on_sent=lambda: self.refresh()).present(self.deck.win)

    def current_view(self) -> FeedView:
        return self.stack.get_visible_child()  # type: ignore[return-value]

    def update_badges(self) -> None:
        for feed, view in self.views.items():
            if feed == HOME or self.spec.kind == "feed":
                continue
            page = self.stack.get_page(view)
            n = view.unread_count()
            page.set_badge_number(n)
            page.set_needs_attention(n > 0)

    def refresh(self, manual: bool = False, skip_live: bool = False) -> None:
        """`skip_live`: Home und Benachrichtigungen kommen schon über den Stream."""
        live = skip_live and self.deck.service.is_live(self.profile)
        for feed, view in self.views.items():
            if live and feed in (HOME, NOTIFICATIONS):
                continue
            view.refresh(manual=manual)


NARROW_BELOW = "max-width: 620sp"


class DandelionDeck(Gtk.Box):
    __gtype_name__ = "DandelionDeck"

    #: Schmal: eine Spalte nach der anderen, Umschalter unten (siehe `_apply_layout`)
    narrow = GObject.Property(type=bool, default=False)

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.role: Role | None = None
        self.columns: list[DeckColumn] = []
        self.current = 0
        self._separators: list[Gtk.Separator] = []
        self._column_buttons: list[Gtk.ToggleButton] = []
        self._timer = 0

        self.columns_box = Gtk.Box()
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                           vscrollbar_policy=Gtk.PolicyType.NEVER,
                                           child=self.columns_box, vexpand=True, hexpand=True)
        self.empty = Adw.StatusPage(icon_name="mail-unread-symbolic",
                                    title=_("Nothing to Read Here"),
                                    description=_("Add a Mastodon or Bluesky profile to this role "
                                                  "to see its timeline."))
        self.empty_button = Gtk.Button(label=_("Roles and Profiles"), halign=Gtk.Align.CENTER)
        self.empty_button.add_css_class("pill")
        self.empty_button.add_css_class("suggested-action")
        self.empty_button.set_action_name("win.manage-roles")
        self.empty.set_child(self.empty_button)
        self.stack = Gtk.Stack(vexpand=True)
        self.stack.add_named(self.scroller, "columns")
        self.stack.add_named(self.empty, "empty")
        self.switcher = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6,
                                margin_start=6, margin_end=6)
        self.switcher.add_css_class("linked")
        self.switcher_bar = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                               vscrollbar_policy=Gtk.PolicyType.NEVER,
                                               child=self.switcher, visible=False)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self.stack)
        content.append(Gtk.Separator())
        content.append(self.switcher_bar)
        self.bin = Adw.BreakpointBin(width_request=300, height_request=200, child=content,
                                     vexpand=True)
        breakpoint_ = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(NARROW_BELOW))
        breakpoint_.add_setter(self, "narrow", True)
        self.bin.add_breakpoint(breakpoint_)
        self.append(self.bin)
        self.connect("notify::narrow", lambda *_a: self._apply_layout())
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)

        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    def setup(self, app: DandelionApplication, win: DandelionWindow) -> None:
        self.app, self.win = app, win
        self.service = app.reader
        self.avatars = AvatarCache(app.http)

    # -- Rolle und Spalten --------------------------------------------------
    def set_role(self, role: Role | None) -> None:
        self.role = role
        self.reload()

    def reload(self) -> None:
        """Baut die Spalten der gewählten Rolle neu auf."""
        while (child := self.columns_box.get_first_child()) is not None:
            self.columns_box.remove(child)
        self.columns = []
        self._separators = []
        specs = self.service.columns(self.role) if self.role is not None else []
        for spec in specs:
            profile = self.app.store.profile(spec.profile_id)
            if profile is None:
                continue
            column = DeckColumn(self, profile, spec)
            if len(specs) == 1:
                column.set_hexpand(True)
            if self.columns:
                sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
                self._separators.append(sep)
                self.columns_box.append(sep)
            self.columns.append(column)
            self.columns_box.append(column)
        self.stack.set_visible_child_name("columns" if self.columns else "empty")
        self.current = min(self.current, max(len(self.columns) - 1, 0))
        self._build_switcher()
        self._apply_layout()
        self._sync_streams()
        self.win.sync_title()

    # -- Schmales Layout ----------------------------------------------------
    def _build_switcher(self) -> None:
        while (child := self.switcher.get_first_child()) is not None:
            self.switcher.remove(child)
        self._column_buttons = []
        group: Gtk.ToggleButton | None = None
        for i, column in enumerate(self.columns):
            button = Gtk.ToggleButton()
            if group is not None:
                button.set_group(group)
            group = group or button
            title = column.spec.title if column.spec.kind == "feed" else column.profile.title
            box = Gtk.Box(spacing=6)
            avatar = Adw.Avatar(size=24, text=column.profile.title, show_initials=True)
            self.avatars.apply(avatar, column.profile.avatar_url)
            overlay = Gtk.Overlay(child=avatar)
            overlay.add_overlay(platform_badge(column.profile.platform))
            box.append(overlay)
            if column.spec.kind == "feed":
                label = Gtk.Label(label=title, ellipsize=Pango.EllipsizeMode.END, max_width_chars=12)
                box.append(label)
            button.set_child(box)
            button.set_tooltip_text(title)
            button.update_property([Gtk.AccessibleProperty.LABEL], [title])
            button.set_active(i == self.current)
            button.connect("toggled", lambda b, i=i: self.select_column(i) if b.get_active() else None)
            self.switcher.append(button)
            self._column_buttons.append(button)

    def select_column(self, index: int) -> None:
        """Zeigt im schmalen Layout die Spalte `index`; im breiten scrollt es dorthin."""
        if not 0 <= index < len(self.columns):
            return
        self.current = index
        if index < len(self._column_buttons) and not self._column_buttons[index].get_active():
            self._column_buttons[index].set_active(True)
        self._apply_layout()

    def _apply_layout(self) -> None:
        narrow = bool(self.narrow)
        self.scroller.set_policy(Gtk.PolicyType.NEVER if narrow else Gtk.PolicyType.AUTOMATIC,
                                 Gtk.PolicyType.NEVER)
        for sep in self._separators:
            sep.set_visible(not narrow)
        for i, column in enumerate(self.columns):
            column.set_visible(not narrow or i == self.current)
            column.set_size_request(0 if narrow else COLUMN_WIDTH, -1)
            column.set_hexpand(narrow or len(self.columns) == 1)
        self.switcher_bar.set_visible(narrow and len(self.columns) > 1)

    def column_count(self) -> int:
        return len(self.columns)

    def _stored_specs(self) -> list[DeckColumnSpec]:
        return list(self.service.columns(self.role)) if self.role is not None else []

    def add_feed_column(self, profile: Profile, feed: str, title: str) -> None:
        """Hängt eine Liste (Hashtag, Liste, Lesezeichen …) als eigene Spalte an."""
        if self.role is None:
            return
        specs = self._stored_specs()
        if any(s.kind == "feed" and s.profile_id == profile.id and s.feed == feed for s in specs):
            self.win.toast(_("{title} is already a column").format(title=title))
            return
        specs.append(DeckColumnSpec(self.role.id, profile.id, "feed", feed, title))  # type: ignore[arg-type]
        self.service.save_columns(self.role, specs)
        self.reload()
        self.win.toast(_("Column added: {title}").format(title=title))
        GLib.idle_add(self._scroll_to_end)

    def remove_column(self, spec: DeckColumnSpec) -> None:
        if self.role is None:
            return
        specs = [s for s in self._stored_specs()
                 if not (s.kind == spec.kind and s.profile_id == spec.profile_id
                         and s.feed == spec.feed)]
        self.service.save_columns(self.role, specs)
        self.reload()

    def edit_columns(self) -> None:
        if self.role is None:
            return
        from .columns_dialog import ColumnsDialog
        dialog = ColumnsDialog(self, self.role)
        dialog.connect("closed", lambda *_a: self.reload())
        dialog.present(self.win)

    def _scroll_to_end(self) -> bool:
        adj = self.scroller.get_hadjustment()
        adj.set_value(adj.get_upper())
        return GLib.SOURCE_REMOVE

    def unread_changed(self) -> None:
        """Ein Lesestand oder Zähler hat sich geändert: Rollenliste auffrischen."""
        if not getattr(self, "_badge_pending", False):
            self._badge_pending = True

            def run() -> bool:
                self._badge_pending = False
                self.win.update_read_badges()
                return GLib.SOURCE_REMOVE
            GLib.idle_add(run)

    def refresh_all(self, manual: bool = True) -> None:
        for column in self.columns:
            column.refresh(manual=manual, skip_live=not manual)

    # -- Live-Verbindung und Abfrage ----------------------------------------
    def _sync_streams(self) -> None:
        if not self.get_mapped():
            self.service.stop_streams()
            return
        wanted = {c.profile.id for c in self.columns
                  if c.spec.kind == "profile" and c.profile.platform == "mastodon"}
        self.service.stop_streams(keep=wanted)  # type: ignore[arg-type]
        for column in self.columns:
            if column.profile.id in wanted:
                self.service.start_stream(column.profile, self._on_stream)

    def _on_stream(self, profile: Profile, feed: str | None) -> None:
        """Neues vom Stream: Liste aus dem Cache ergänzen, bei `None` (neu verbunden) nachladen."""
        for column in self.columns:
            if column.profile.id != profile.id or column.spec.kind != "profile":
                continue
            if feed is None:
                for f in (HOME, NOTIFICATIONS):
                    if f in column.views:
                        column.views[f].refresh(manual=False)
            elif feed in column.views:
                column.views[feed].merge_cache()
        self.unread_changed()

    def _on_map(self, *_args: object) -> None:
        if not self._timer:
            self._timer = GLib.timeout_add_seconds(POLL_SECONDS, self._poll)
        self.refresh_all(manual=False)
        self._sync_streams()

    def _on_unmap(self, *_args: object) -> None:
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        self.service.stop_streams()

    def _poll(self) -> bool:
        self.refresh_all(manual=False)
        return GLib.SOURCE_CONTINUE

    # -- Tastatur -----------------------------------------------------------
    def _focused_row(self) -> tuple[Gtk.ListBoxRow | None, FeedView | None, DeckColumn | None]:
        widget = self.win.get_focus()
        row = view = column = None
        while widget is not None and widget is not self:
            if isinstance(widget, Gtk.ListBoxRow) and row is None:
                row = widget
            elif isinstance(widget, FeedView) and view is None:
                view = widget
            elif isinstance(widget, DeckColumn):
                column = widget
                break
            widget = widget.get_parent()
        return row, view, column

    def _focus_row(self, view: FeedView, index: int) -> bool:
        row = view.listbox.get_row_at_index(max(index, 0))
        if row is None:
            return False
        row.grab_focus()
        return True

    def focus_first(self) -> bool:
        if self.columns:
            self._focus_row(self.columns[0].current_view(), 0)
        return GLib.SOURCE_REMOVE

    def _on_key(self, _ctrl: Gtk.EventControllerKey, keyval: int, _code: int,
                state: Gdk.ModifierType) -> bool:
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK
                    | Gdk.ModifierType.SUPER_MASK) or not self.columns:
            return False
        focus = self.win.get_focus()
        if isinstance(focus, (Gtk.Editable, Gtk.TextView)):
            return False
        key = (Gdk.keyval_name(keyval) or "").lower()
        row, view, column = self._focused_row()
        if column is None:
            column = self.columns[0]
        view = view or column.current_view()
        index = row.get_index() if row is not None else -1

        if key in ("j", "k"):
            self._focus_row(view, index + 1 if key == "j" else index - 1)
        elif key == "g":
            self._focus_row(view, 0)
            view.scroller.get_vadjustment().set_value(0)
        elif key in ("h", "l"):
            i = self.columns.index(column) + (1 if key == "l" else -1)
            if 0 <= i < len(self.columns):
                self.select_column(i)
                self._focus_row(self.columns[i].current_view(), max(index, 0))
        elif key in ("1", "2", "3"):
            feeds = list(column.views)
            n = int(key) - 1
            if n < len(feeds):
                column.stack.set_visible_child_name(feeds[n])
        elif key == "n":
            column.new_post()
        elif row is not None and key in ("r", "f", "b", "m", "o"):
            self._row_action(row, key)
        else:
            return False
        return True

    def _row_action(self, row: Gtk.ListBoxRow, key: str) -> None:
        buttons = getattr(row.get_child(), "action_buttons", None)
        if not buttons:
            return
        if key == "r":
            buttons["reply"].emit("clicked")
        elif key == "o":
            buttons["open"]()
        else:
            toggle = buttons[{"f": "favourite", "b": "boost", "m": "bookmark"}[key]]
            if toggle.get_sensitive():
                toggle.set_active(not toggle.get_active())
