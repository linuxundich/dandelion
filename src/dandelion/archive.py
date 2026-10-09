# SPDX-License-Identifier: GPL-3.0-or-later
"""Seitenleiste: Kalender, Entwürfe, geplante und veröffentlichte Beiträge."""

from __future__ import annotations

from datetime import datetime
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gio, GLib, Gtk

from .core.models import Post, PostState
from .schedule_dialog import format_when
from .util import first_line, format_time

if TYPE_CHECKING:
    from .application import DandelionApplication
    from .window import DandelionWindow

DRAFT_STATES = (PostState.DRAFT,)
SCHEDULED_STATES = (PostState.MISSED, PostState.SCHEDULED, PostState.PAUSED)
PUBLISHED_STATES = (PostState.SENDING, PostState.PUBLISHED, PostState.PARTIAL, PostState.FAILED)
PUBLISHED_LIMIT = 5
SEARCH_LIMIT = 30

# Art eines Eintrags; zusammen mit der Beitrags-ID der Schlüssel für die Auswahl
CALENDAR, NEW, DRAFT, SCHEDULED, PUBLISHED, ALL = (
    "calendar", "new", "draft", "scheduled", "published", "all")

Key = tuple[str, int | None]


def fts_query(text: str) -> str | None:
    words = text.replace('"', " ").split()
    return " ".join(f'"{w}"*' for w in words) if words else None


class Archive:
    """Füllt die Adw.Sidebar und übersetzt Klicks und Kontextmenüs in Aktionen."""

    def __init__(self, app: DandelionApplication, win: DandelionWindow,
                 sidebar: Adw.Sidebar, menus: dict[str, Gio.MenuModel]) -> None:
        self.app, self.win, self.sidebar, self.menus = app, win, sidebar, menus
        self.entries: list[Key] = []
        self.query = ""
        self._menu_key: Key | None = None
        self._pending = 0

        self.actions = Gio.SimpleActionGroup()
        for name, cb in (
            ("duplicate", self._duplicate),
            ("delete-draft", lambda post: self.win.composer.delete_draft(post.id)),
            ("reschedule", lambda post: self.win.scheduled.reschedule(post)),
            ("pause", lambda post: self.win.scheduled.toggle_pause(post)),
            ("resume", lambda post: self.win.scheduled.toggle_pause(post)),
            ("send-now", lambda post: self.win.scheduled.send_now(post)),
            ("to-drafts", lambda post: self.win.scheduled.to_drafts(post)),
            ("delete-scheduled", lambda post: self.win.scheduled.delete_post(post)),
            ("reuse", lambda post: self.win.history.reuse(post)),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=cb: self._run(cb))
            self.actions.add_action(action)
        sidebar.insert_action_group("archive", self.actions)

    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Baut die Leiste beim nächsten Leerlauf neu auf (mehrere Aufrufe bündeln)."""
        if not self._pending:
            self._pending = GLib.idle_add(self._rebuild)

    def set_query(self, text: str) -> None:
        self.query = text.strip()
        self.reload()

    def sync_selection(self) -> None:
        key = self.win.current_key()
        try:
            index = self.entries.index(key)
        except ValueError:
            index = Gtk.INVALID_LIST_POSITION
        if self.sidebar.get_selected() != index:
            self.sidebar.set_selected(index)

    def activate(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        kind, post_id = self.entries[index]
        if kind == CALENDAR:
            self.win.show_view("scheduled")
        elif kind == ALL:
            self.win.show_view("history")
        elif kind == NEW:
            self.win.show_view("composer")
        elif kind == PUBLISHED and post_id is not None:
            self.win.show_post(post_id)
        elif post_id is not None:
            self.win.composer.edit_post(post_id)

    def setup_menu(self, item: Adw.SidebarItem | None) -> None:
        if item is None:
            return
        index = item.get_index()
        self._menu_key = self.entries[index] if 0 <= index < len(self.entries) else None
        post = self._menu_post()
        state = post.state if post else None
        enabled = {
            "duplicate": post is not None,
            "delete-draft": post is not None,
            "pause": state == PostState.SCHEDULED,
            "resume": state == PostState.PAUSED,
            "send-now": state in (PostState.SCHEDULED, PostState.PAUSED, PostState.MISSED),
        }
        for name in self.actions.list_actions():
            action = self.actions.lookup_action(name)
            action.set_enabled(enabled.get(name, post is not None))  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    def _menu_post(self) -> Post | None:
        if not self._menu_key or self._menu_key[1] is None:
            return None
        return self.app.store.load_post(self._menu_key[1])

    def _run(self, cb) -> None:  # type: ignore[no-untyped-def]
        post = self._menu_post()
        if post is not None:
            cb(post)

    def _duplicate(self, post: Post) -> None:
        if post.id == self.win.composer.post.id:
            self.win.composer.save_now()
            post = self.app.store.load_post(post.id) or post  # type: ignore[arg-type]
        self.win.scheduled.duplicate(post)

    def _rebuild(self) -> bool:
        self._pending = 0
        store = self.app.store
        roles = {r.id: r for r in store.roles()}
        platforms = {p.id: p.platform for p in store.profiles()}
        search = fts_query(self.query)
        current = self.win.composer.post if self.win.composer.app else None
        self.sidebar.remove_all()
        self.entries = []

        if not search:
            section = Adw.SidebarSection()
            self._add(section, (CALENDAR, None),
                      Adw.SidebarItem(title=_("Calendar"), icon_name="x-office-calendar-symbolic"))
            self.sidebar.append(section)

        # Entwürfe; der gerade geöffnete leere Beitrag erscheint als „Neuer Beitrag“
        section = self._section(_("Drafts"), DRAFT)
        if current is not None and current.id is None and current.state == PostState.DRAFT \
                and not search:
            self._add(section, (NEW, None), self._item(current, roles, platforms,
                                                      _("New Post"), _("Not saved yet")))
        ids = store.post_ids(DRAFT_STATES, search=search,
                             limit=SEARCH_LIMIT if search else 500)
        for pid in ids:
            post = store.load_post(pid)
            if post is None or (post.is_empty() and (current is None or post.id != current.id)):
                continue
            role = roles.get(post.role_id)
            subtitle = " · ".join(x for x in (role.name if role else "",
                                              format_time(post.updated_at)) if x)
            self._add(section, (DRAFT, pid), self._item(post, roles, platforms, None, subtitle))
        self._finish(section)

        section = self._section(_("Scheduled"), SCHEDULED)
        for pid in store.post_ids(SCHEDULED_STATES, order="scheduled_at", search=search,
                                  limit=SEARCH_LIMIT if search else 500):
            post = store.load_post(pid)
            if post is None:
                continue
            when = format_when(datetime.fromisoformat(post.scheduled_at), post.timezone) \
                if post.scheduled_at else _("Without Date")
            if post.state == PostState.MISSED:
                when = _("Missed") + " · " + when
            elif post.state == PostState.PAUSED:
                when = _("Paused") + " · " + when
            item = self._item(post, roles, platforms, None, when)
            self._add(section, (SCHEDULED, pid), item)
        self._finish(section)

        section = self._section(_("Published"), PUBLISHED)
        order = "COALESCE(published_at, updated_at) DESC"
        limit = SEARCH_LIMIT if search else PUBLISHED_LIMIT
        ids = store.post_ids(PUBLISHED_STATES, order=order, search=search, limit=limit)
        for pid in ids:
            post = store.load_post(pid)
            if post is None:
                continue
            role = roles.get(post.role_id)
            subtitle = " · ".join(x for x in (format_time(post.published_at or post.updated_at),
                                              role.name if role else "") if x)
            self._add(section, (PUBLISHED, pid), self._item(post, roles, platforms, None, subtitle))
        if not search and len(ids) == PUBLISHED_LIMIT:
            total = len(store.post_ids(PUBLISHED_STATES, limit=100000))
            self._add(section, (ALL, None), Adw.SidebarItem(
                title=_("Show All ({n})").format(n=total), icon_name="view-list-symbolic"))
        self._finish(section)

        self.sync_selection()
        return False

    def _section(self, title: str, kind: str) -> Adw.SidebarSection:
        section = Adw.SidebarSection(title=title)
        menu = self.menus.get(kind)
        if menu is not None:
            section.set_menu_model(menu)
        return section

    def _finish(self, section: Adw.SidebarSection) -> None:
        if section.get_items().get_n_items():
            self.sidebar.append(section)

    def _add(self, section: Adw.SidebarSection, key: Key, item: Adw.SidebarItem) -> None:
        # Der Index in self.entries entspricht dem Index in der ganzen Leiste,
        # weil Abschnitte ohne Einträge gar nicht erst angehängt werden.
        section.append(item)
        self.entries.append(key)

    def _item(self, post: Post, roles, platforms, title: str | None,  # type: ignore[no-untyped-def]
              subtitle: str) -> Adw.SidebarItem:
        item = Adw.SidebarItem(title=title or first_line(post.body, 60) or _("Empty Post"),
                               subtitle=subtitle)
        role = roles.get(post.role_id)
        if role and role.emoji:
            emoji = Gtk.Label(label=role.emoji)
            emoji.add_css_class("sidebar-emoji")
            item.set_prefix(emoji)
        else:
            item.set_icon_name("document-edit-symbolic")

        suffix = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
        if post.state == PostState.MISSED:
            icon = Gtk.Image(icon_name="appointment-missed-symbolic", tooltip_text=_("Missed"))
            icon.add_css_class("warning")
            suffix.append(icon)
        elif post.state == PostState.PAUSED:
            suffix.append(Gtk.Image(icon_name="media-playback-pause-symbolic",
                                    tooltip_text=_("Paused")))
        elif post.state in (PostState.FAILED, PostState.PARTIAL):
            icon = Gtk.Image(icon_name="dialog-error-symbolic", tooltip_text=_("Not published"))
            icon.add_css_class("error")
            suffix.append(icon)
        elif post.state == PostState.SENDING:
            suffix.append(Adw.Spinner())
        seen: list[str] = []
        for t in post.targets:
            platform = platforms.get(t.profile_id)
            if t.enabled and platform and platform not in seen:
                seen.append(platform)
        dots = Gtk.Box(spacing=3, valign=Gtk.Align.CENTER)
        for platform in seen:
            dot = Gtk.Box(valign=Gtk.Align.CENTER)
            dot.add_css_class("platform-dot")
            dot.add_css_class("sidebar-dot")
            dot.add_css_class(f"platform-{platform}")
            dots.append(dot)
        if seen:
            suffix.append(dots)
        if suffix.get_first_child() is not None:
            item.set_suffix(suffix)
        return item
