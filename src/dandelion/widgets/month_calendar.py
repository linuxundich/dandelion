# SPDX-License-Identifier: GPL-3.0-or-later
"""Monatskalender: geplante und veröffentlichte Beiträge, freie Zeitfenster, Ziehen und Ablegen."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from gettext import gettext as _
from gettext import ngettext

from gi.repository import Gdk, GLib, GObject, Gtk

from ..core.models import Post, PostState, Role
from ..util import first_line, label_widget

MAX_ENTRIES = 3
PUBLISHED_STATES = (PostState.PUBLISHED, PostState.PARTIAL, PostState.FAILED, PostState.SENDING)


def post_time(post: Post) -> datetime | None:
    """Zeitpunkt, an dem ein Beitrag im Kalender steht (geplant oder veröffentlicht)."""
    iso = post.published_at if post.state in PUBLISHED_STATES else post.scheduled_at
    return datetime.fromisoformat(iso).astimezone() if iso else None


class DandelionMonthCalendar(Gtk.Box):
    __gtype_name__ = "DandelionMonthCalendar"
    __gsignals__ = {
        "post-activated": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        # Beitrags-ID, Jahr, Monat, Tag
        "post-moved": (GObject.SignalFlags.RUN_FIRST, None, (int, int, int, int)),
        "month-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # Jahr, Monat, Tag (nur im kompakten Modus)
        "day-selected": (GObject.SignalFlags.RUN_FIRST, None, (int, int, int)),
    }

    _compact = False

    def do_constructed(self) -> None:
        # Läuft auch, wenn GtkBuilder das Widget aus dem Blueprint erzeugt
        # (dann wird Pythons __init__ nicht aufgerufen).
        Gtk.Box.do_constructed(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self._compact = False
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today
        self._posts: list[tuple[Post, Role | None]] = []
        self._slots: list[tuple[datetime, Role]] = []

        self.grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=False, column_spacing=6,
                             row_spacing=6, vexpand=True)
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

    def title(self) -> str:
        return GLib.DateTime.new_local(self.year, self.month, 1, 0, 0, 0).format("%B %Y") or ""

    def month_range(self) -> tuple[date, date]:
        """Erster und letzter sichtbarer Tag (inklusive der Tage der Nachbarmonate)."""
        first = date(self.year, self.month, 1)
        start = first - timedelta(days=first.weekday())
        days = 35 if (start + timedelta(days=35)).month != self.month else 42
        return start, start + timedelta(days=days - 1)

    def set_posts(self, posts: list[tuple[Post, Role | None]],
                  slots: list[tuple[datetime, Role]] | None = None) -> None:
        self._posts = posts
        self._slots = slots or []
        self._rebuild()

    def entries_for(self, day: date) -> list[tuple[datetime, Post, Role | None]]:
        out = []
        for post, role in self._posts:
            when = post_time(post)
            if when and when.date() == day:
                out.append((when, post, role))
        return sorted(out, key=lambda x: x[0])

    def shift(self, delta: int) -> None:
        month = self.month + delta
        self.year += (month - 1) // 12
        self.month = (month - 1) % 12 + 1
        self._rebuild()
        self.emit("month-changed")

    def go_today(self) -> None:
        today = date.today()
        self.year, self.month = today.year, today.month
        self.selected = today
        self._rebuild()
        self.emit("month-changed")
        self.emit("day-selected", today.year, today.month, today.day)

    # -- Aufbau ----------------------------------------------------------------
    def _rebuild(self) -> None:
        while (child := self.grid.get_first_child()) is not None:
            self.grid.remove(child)
        names = [calendar.day_abbr[i] for i in range(7)]
        for col, name in enumerate(names):
            label = Gtk.Label(label=name[:2] if self._compact else name,
                              xalign=0.5 if self._compact else 0)
            label.add_css_class("caption-heading")
            label.add_css_class("dim-label")
            if not self._compact:
                label.set_margin_start(6)
            self.grid.attach(label, col, 0, 1, 1)
        # Tageszeilen teilen sich die Höhe (vexpand der Zellen), die Kopfzeile nicht

        by_day: dict[date, list[tuple[datetime, Post, Role | None]]] = {}
        for post, role in self._posts:
            when = post_time(post)
            if when:
                by_day.setdefault(when.date(), []).append((when, post, role))
        slots: dict[date, list[tuple[datetime, Role]]] = {}
        for when, role in self._slots:
            slots.setdefault(when.date(), []).append((when, role))

        start, end = self.month_range()
        today = date.today()
        day, i = start, 0
        while day <= end:
            cell = self._cell(day, sorted(by_day.get(day, []), key=lambda x: x[0]),
                              sorted(slots.get(day, []), key=lambda x: x[0]),
                              day.month == self.month, day == today)
            self.grid.attach(cell, i % 7, 1 + i // 7, 1, 1)
            day += timedelta(days=1)
            i += 1

    def _cell(self, day: date, entries: list[tuple[datetime, Post, Role | None]],
              slots: list[tuple[datetime, Role]], in_month: bool,
              is_today: bool) -> Gtk.Widget:
        cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, vexpand=not self._compact)
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
            if day == self.selected:
                cell.add_css_class("selected-day")
            if entries:
                dots = Gtk.Box(spacing=2, halign=Gtk.Align.CENTER)
                for _when, _post, role in entries[:4]:
                    dot = Gtk.Box(width_request=6, height_request=6)
                    dot.add_css_class("cal-dot")
                    dot.add_css_class(f"role-bg-{role.color if role else 'slate'}")
                    dots.append(dot)
                cell.append(dots)
            click = Gtk.GestureClick()
            click.connect("released", lambda *_a, d=day: self._select(d))
            cell.add_controller(click)
        else:
            for when, post, role in entries[:MAX_ENTRIES]:
                cell.append(self._entry(when, post, role))
            room = MAX_ENTRIES - len(entries)
            for when, role in slots[:max(0, room)]:
                cell.append(self._slot(when, role))
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

    def _select(self, day: date) -> None:
        self.selected = day
        self._rebuild()
        self.emit("day-selected", day.year, day.month, day.day)

    def _entry(self, when: datetime, post: Post, role: Role | None) -> Gtk.Widget:
        published = post.state in PUBLISHED_STATES
        mark = "✓ " if post.state == PostState.PUBLISHED else ""
        text = f"{when:%H:%M} {mark}{role.emoji if role else ''} {first_line(post.body, 40)}"
        button = Gtk.Button()
        label = Gtk.Label(label=text, xalign=0, ellipsize=3)
        button.set_child(label)
        button.add_css_class("flat")
        button.add_css_class("cal-entry")
        button.add_css_class(f"role-{role.color if role else 'slate'}")
        state = ""
        if published:
            button.add_css_class("published")
            state = _("published")
        elif post.state == PostState.PAUSED:
            button.add_css_class("paused")
            state = _("paused")
        elif post.state == PostState.MISSED:
            button.add_css_class("missed")
            state = _("missed")
        label_widget(button, f"{when:%H:%M} {first_line(post.body, 80)}"
                     + (f" ({state})" if state else ""))
        button.connect("clicked", lambda *_a: self.emit("post-activated", post.id))
        if not published:
            source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
            source.connect("prepare", lambda *_a: Gdk.ContentProvider.new_for_value(str(post.id)))
            source.connect("drag-begin", lambda src, _d: src.set_icon(
                Gtk.WidgetPaintable.new(button), 0, 0))
            button.add_controller(source)
        return button

    @staticmethod
    def _slot(when: datetime, role: Role) -> Gtk.Widget:
        label = Gtk.Label(label=_("{time} free").format(time=f"{when:%H:%M}"), xalign=0,
                          ellipsize=3)
        label.add_css_class("cal-slot")
        label.set_tooltip_text(_("Free time slot of “{role}”").format(role=role.name))
        return label

    def _dropped(self, value: str, day: date) -> bool:
        try:
            post_id = int(value)
        except (TypeError, ValueError):
            return False
        self.emit("post-moved", post_id, day.year, day.month, day.day)
        return True
