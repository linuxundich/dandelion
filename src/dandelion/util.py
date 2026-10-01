# SPDX-License-Identifier: GPL-3.0-or-later
"""Kleine Hilfen für die Oberfläche."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from gettext import gettext as _
from typing import Any

from gi.repository import GLib

log = logging.getLogger(__name__)
_tasks: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any],
          on_error: Callable[[BaseException], None] | None = None) -> asyncio.Task[Any]:
    """Startet eine Koroutine in der GLib-Hauptschleife und hält eine Referenz."""
    task = asyncio.ensure_future(coro)
    _tasks.add(task)

    def done(t: asyncio.Task[Any]) -> None:
        _tasks.discard(t)
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            if on_error:
                on_error(exc)
            else:
                log.error("Hintergrundaufgabe fehlgeschlagen", exc_info=exc)

    task.add_done_callback(done)
    return task


class Debouncer:
    def __init__(self, delay_ms: int, callback: Callable[[], None]) -> None:
        self.delay_ms = delay_ms
        self.callback = callback
        self._source = 0

    def __call__(self, *_args: Any) -> None:
        if self._source:
            GLib.source_remove(self._source)
        self._source = GLib.timeout_add(self.delay_ms, self._fire)

    def _fire(self) -> bool:
        self._source = 0
        self.callback()
        return GLib.SOURCE_REMOVE

    def flush(self) -> None:
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0
            self.callback()


def format_time(iso: str | None) -> str:
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso).astimezone()
    now = datetime.now().astimezone()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    if (now.date() - dt.date()).days == 1:
        return _("Yesterday") + dt.strftime(" %H:%M")
    return dt.strftime("%d.%m.%Y %H:%M") if dt.year != now.year else dt.strftime("%d.%m. %H:%M")


def day_label(iso: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone()
    now = datetime.now().astimezone()
    delta = (now.date() - dt.date()).days
    if delta == 0:
        return _("Today")
    if delta == 1:
        return _("Yesterday")
    return dt.strftime("%A, %d. %B %Y")


def first_line(text: str, limit: int = 80) -> str:
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return line if len(line) <= limit else line[: limit - 1] + "…"


# Sprachen für die Auswahl im Composer (BCP 47, Eigenname)
LANGUAGES = [
    ("de", "Deutsch"), ("en", "English"), ("fr", "Français"), ("es", "Español"),
    ("it", "Italiano"), ("nl", "Nederlands"), ("pl", "Polski"), ("pt", "Português"),
    ("sv", "Svenska"), ("da", "Dansk"), ("nb", "Norsk bokmål"), ("fi", "Suomi"),
    ("cs", "Čeština"), ("tr", "Türkçe"), ("uk", "Українська"), ("ru", "Русский"),
    ("el", "Ελληνικά"), ("ja", "日本語"), ("zh", "中文"), ("ko", "한국어"), ("ar", "العربية"),
]


def system_language() -> str:
    for name in GLib.get_language_names():
        code = name.split("_")[0].split(".")[0]
        if any(code == c for c, _n in LANGUAGES):
            return code
    return "en"


VISIBILITY_LABELS = {
    "public": (_("Public"), "earth-symbolic"),
    "unlisted": (_("Quiet Public"), "weather-clear-night-symbolic"),
    "private": (_("Followers Only"), "system-users-symbolic"),
    "direct": (_("Mentioned Only"), "mail-unread-symbolic"),
}

CONTENT_LABEL_NAMES = {
    "": _("No Label"),
    "sexual": _("Suggestive"),
    "nudity": _("Nudity"),
    "porn": _("Adult Content"),
    "graphic-media": _("Graphic Media"),
}


def icon_button(icon: str, label: str, **kwargs: object) -> "Gtk.Button":
    """Symbolknopf mit Tooltip und Accessible-Label (Screenreader lesen sonst nichts)."""
    from gi.repository import Gtk
    button = Gtk.Button(icon_name=icon, tooltip_text=label, **kwargs)
    button.update_property([Gtk.AccessibleProperty.LABEL], [label])
    return button


def label_widget(widget: "Gtk.Widget", label: str) -> None:
    from gi.repository import Gtk
    widget.set_tooltip_text(label)
    widget.update_property([Gtk.AccessibleProperty.LABEL], [label])
