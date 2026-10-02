# SPDX-License-Identifier: GPL-3.0-or-later
"""Monatskalender für geplante Beiträge mit Ziehen und Ablegen."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Gdk, GLib, GObject, Gtk

from ..core.models import Post, PostState, Role
from ..util import first_line, label_widget

MAX_ENTRIES = 3


class DandelionMonthCalendar(Gtk.Box):
    __gtype_name__ = "DandelionMonthCalendar"
    __gsignals__ = {
        "post-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        # Beitrags-ID, Jahr, Monat, Tag
        "post-moved": (GObject.SignalFlags.RUN_FIRST, None, (int, int, int, int)),
    }

    _compact = False

    def do_constructed(self) -> None:
        # Läuft auch, wenn GtkBuilder das Widget aus dem Blueprint erzeugt
        # (dann wird Pythons __init__ nicht aufgerufen).
        Gtk.Box.do_constructed(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(8)
        self._compact = False
        today = date.today()
        self.year, self.month = today.year, today.month
        self._posts: list[tuple[Post, Role | None]] = []

        head = Gtk.Box(spacing=6)
        prev = Gtk.Button(icon_name="go-previous-symbolic")
        label_widget(prev, _("Previous Month"))
        prev.connect("clicked", lambda *_: self._shift(-1))
        nxt = Gtk.Button(icon_name="go-next-symbolic")
        label_widget(nxt, _("Next Month"))
        nxt.connect("clicked", lambda *_: self._shift(1))
        for b in (prev, nxt):
            b.add_css_class("flat")
        self.title = Gtk.Label(hexpand=True, xalign=0)
        self.title.add_css_class("title-4")
        today_btn = Gtk.Button(label=_("_Today"), use_underline=True)
        today_btn.add_css_class("flat")
        today_btn.connect("clicked", lambda *_: self._go_today())
        head.append(self.title)
        head.append(today_btn)
        head.append(prev)
        head.append(nxt)
        self.append(head)

        self.grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=False, column_spacing=4,
                             row_spacing=4)
        self.grid.add_css_class("month-grid")
        self.append(self.grid)
        self._rebuild()

    # -- Eigenschaften -------------------------------------------------------
    @GObject.Property(type=bool, default=False)
    def compact(self) -> bool:
        return self._compact

    @compact.setter  # type: ignore[no-redef]
    def compact(self, value: bool) -> None:
        if value != self._compact:
            self._compact = value
            self._rebuild()

    def set_posts(self, posts: list[tuple[Post, Role | None]]) -> None:
        self._posts = posts
        self._rebuild()

    def _shift(self, delta: int) -> None:
        month = self.month + delta
        self.year += (month - 1) // 12
        self.month = (month - 1) % 12 + 1
        self._rebuild()

    def _go_today(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self._rebuild()

    # -- Aufbau ----------------------------------------------------------------
    def _rebuild(self) -> None:
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)
        first = date(self.year, self.month, 1)
        self.title.set_label(GLib.DateTime.new_local(self.year, self.month, 1, 0, 0, 0)
                             .format("%B %Y"))
        names = [calendar.day_abbr[i] for i in range(7)]
        for col, name in enumerate(names):
            label = Gtk.Label(label=name[:2] if self._compact else name)
            label.add_css_class("caption-heading")
            label.add_css_class("dim-label")
            self.grid.attach(label, col, 0, 1, 1)

        by_day: dict[date, list[tuple[datetime, Post, Role | None]]] = {}
        for post, role in self._posts:
            if not post.scheduled_at:
                continue
            when = datetime.fromisoformat(post.scheduled_at).astimezone()
            by_day.setdefault(when.date(), []).append((when, post, role))

        start = first - timedelta(days=first.weekday())
        today = date.today()
        for i in range(42):
            day = start + timedelta(days=i)
            if i >= 35 and day.month != self.month:
                break
            cell = self._cell(day, sorted(by_day.get(day, []), key=lambda x: x[0]),
                              day.month == self.month, day == today)
            self.grid.attach(cell, i % 7, 1 + i // 7, 1, 1)

    def _cell(self, day: date, entries: list[tuple[datetime, Post, Role | None]],
              in_month: bool, is_today: bool) -> Gtk.Widget:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        cell.add_css_class("day-cell")
        if not in_month:
            cell.add_css_class("other-month")
        if is_today:
            cell.add_css_class("today")
        cell.set_size_request(-1, 44 if self._compact else 96)
        number = Gtk.Label(label=str(day.day), xalign=0 if not self._compact else 0.5)
        number.add_css_class("day-number")
        cell.append(number)
        a11y = ngettext("{day}: {n} post", "{day}: {n} posts", len(entries)).format(
            day=day.strftime("%d.%m.%Y"), n=len(entries))
        cell.update_property([Gtk.AccessibleProperty.LABEL], [a11y])

        if self._compact:
            if entries:
                dots = Gtk.Box(spacing=2, halign=Gtk.Align.CENTER)
                for _when, post, role in entries[:4]:
                    dot = Gtk.Box(width_request=6, height_request=6)
                    dot.add_css_class("cal-dot")
                    dot.add_css_class(f"role-bg-{role.color if role else 'slate'}")
                    dots.append(dot)
                cell.append(dots)
                click = Gtk.GestureClick()
                click.connect("released", lambda *_a, p=entries[0][1]:
                              self.emit("post-activated", p.id))
                cell.add_controller(click)
        else:
            for when, post, role in entries[:MAX_ENTRIES]:
                cell.append(self._entry(when, post, role))
            if len(entries) > MAX_ENTRIES:
                more = Gtk.Label(label=_("+{n} more").format(n=len(entries) - MAX_ENTRIES),
                                 xalign=0)
                more.add_css_class("caption")
                more.add_css_class("dim-label")
                cell.append(more)

        target = Gtk.DropTarget.new(GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        target.connect("drop", lambda _t, value, _x, _y, d=day: self._dropped(value, d))
        target.connect("enter", lambda *_a: (cell.add_css_class("drop-hover"),
                                             Gdk.DragAction.MOVE)[1])
        target.connect("leave", lambda *_a: cell.remove_css_class("drop-hover"))
        cell.add_controller(target)
        return cell

    def _entry(self, when: datetime, post: Post, role: Role | None) -> Gtk.Widget:
        text = f"{when:%H:%M} {role.emoji if role else ''} {first_line(post.body, 40)}"
        button = Gtk.Button()
        label = Gtk.Label(label=text, xalign=0, ellipsize=3)
        button.set_child(label)
        button.add_css_class("flat")
        button.add_css_class("cal-entry")
        button.add_css_class(f"role-{role.color if role else 'slate'}")
        if post.state == PostState.PAUSED:
            button.add_css_class("paused")
        elif post.state == PostState.MISSED:
            button.add_css_class("missed")
        state = {PostState.PAUSED: _("paused"), PostState.MISSED: _("missed")}.get(post.state, "")
        label_widget(button, f"{when:%H:%M} {first_line(post.body, 80)}"
                     + (f" ({state})" if state else ""))
        button.connect("clicked", lambda *_a: self.emit("post-activated", post.id))
        source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        source.connect("prepare", lambda *_a: Gdk.ContentProvider.new_for_value(str(post.id)))
        source.connect("drag-begin", lambda src, _d: src.set_icon(
            Gtk.WidgetPaintable.new(button), 0, 0))
        button.add_controller(source)
        return button

    def _dropped(self, value: str, day: date) -> bool:
        try:
            post_id = int(value)
        except (TypeError, ValueError):
            return False
        self.emit("post-moved", post_id, day.year, day.month, day.day)
        return True
