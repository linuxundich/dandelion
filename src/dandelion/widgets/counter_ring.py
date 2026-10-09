# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import math

import cairo
from gi.repository import Adw, Graphene, Gtk


class DandelionCounterRing(Gtk.Widget):
    """Ring mit den verbleibenden Zeichen des strengsten Profils (wie in Tuba)."""

    __gtype_name__ = "DandelionCounterRing"

    SIZE = 32
    WIDTH = 3.0

    def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self._ratio = 0.0
        self.label = Gtk.Label()
        self.label.add_css_class("counter-ring-label")
        self.label.add_css_class("numeric")
        self.label.set_parent(self)
        self.add_css_class("counter-ring")

    def do_dispose(self) -> None:
        if self.label is not None:
            self.label.unparent()
            self.label = None  # type: ignore[assignment]
        super().do_dispose()

    def set_count(self, used: int, limit: int) -> None:
        left = limit - used
        self._ratio = min(1.0, used / limit) if limit else 0.0
        self.label.set_label(str(left) if abs(left) < 1000 else f"{left // 1000}k")
        for cls in ("warning", "error"):
            self.remove_css_class(cls)
        if left < 0:
            self.add_css_class("error")
        elif self._ratio >= 0.9:
            self.add_css_class("warning")
        self.queue_draw()

    def do_measure(self, orientation: Gtk.Orientation, for_size: int) -> tuple[int, int, int, int]:
        _lmin, lnat, _a, _b = self.label.measure(orientation, -1)
        size = max(self.SIZE, lnat + 8)
        return size, size, -1, -1

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        self.label.allocate(width, height, baseline, None)

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        w, h = self.get_width(), self.get_height()
        color = self.get_color()
        rect = Graphene.Rect().init(0, 0, w, h)
        cr = snapshot.append_cairo(rect)
        r = min(w, h) / 2 - self.WIDTH / 2 - 1
        cx, cy = w / 2, h / 2
        cr.set_line_width(self.WIDTH)
        cr.set_source_rgba(color.red, color.green, color.blue, 0.15)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()
        if self._ratio > 0:
            accent = color if self.has_css_class("warning") or self.has_css_class("error") \
                else self._accent()
            cr.set_source_rgba(accent.red, accent.green, accent.blue, 1.0)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * self._ratio)
            cr.stroke()
        self.snapshot_child(self.label, snapshot)

    @staticmethod
    def _accent():  # type: ignore[no-untyped-def]
        return Adw.StyleManager.get_default().get_accent_color_rgba()
