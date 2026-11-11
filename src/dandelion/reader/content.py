# SPDX-License-Identifier: GPL-3.0-or-later
"""Mastodon-HTML in Pango-Markup umwandeln, ohne WebView.

Erlaubt sind Absätze, Zeilenumbrüche, Links, fett, kursiv, durchgestrichen,
Code und Zitate. Alles andere wird auf den Text reduziert. Das Ergebnis ist
immer wohlgeformt, damit `Gtk.Label.set_markup` nie scheitert.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from gettext import gettext as _
from html.parser import HTMLParser

_INLINE = {"strong": "b", "b": "b", "em": "i", "i": "i", "del": "s", "s": "s",
           "code": "tt", "u": "u"}
_BLOCK = {"p", "div", "blockquote", "pre", "ul", "ol", "li", "h1", "h2", "h3", "h4", "h5", "h6"}


class _Converter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []     # offene Pango-Tags
        self.skip = 0                  # Tiefe in unsichtbarem Text
        self.span_stack: list[str] = []
        self.pending_break = 0
        self.list_depth = 0

    # -- Hilfen ----------------------------------------------------------
    def _break(self, n: int) -> None:
        if self.out:
            self.pending_break = max(self.pending_break, n)

    def _flush_break(self) -> None:
        if self.pending_break:
            self.out.append("\n" * self.pending_break)
            self.pending_break = 0

    # -- Parser ----------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        classes = a.get("class", "").split()
        if tag == "br":
            self.out.append("\n")
            return
        if tag == "span":
            hidden = "invisible" in classes
            if hidden:
                self.skip += 1
            self.span_stack.append("hidden" if hidden else "ellipsis" if "ellipsis" in classes else "")
            return
        if tag in _BLOCK:
            self._break(1 if tag in ("li", "div") else 2)
            if tag == "li":
                self._flush_break()
                self.out.append("• ")
            return
        if tag == "a":
            href = a.get("href", "")
            if href.startswith(("http://", "https://")) and not self.skip:
                self._flush_break()
                self.out.append(f'<a href="{html.escape(href, quote=True)}">')
                self.stack.append("a")
            else:
                self.stack.append("")
            return
        if tag in _INLINE and not self.skip:
            self._flush_break()
            self.out.append(f"<{_INLINE[tag]}>")
            self.stack.append(_INLINE[tag])
            return
        if tag in _INLINE:
            self.stack.append("")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span":
            kind = self.span_stack.pop() if self.span_stack else ""
            if kind == "hidden":
                self.skip -= 1
            elif kind == "ellipsis" and not self.skip:
                self._flush_break()
                self.out.append("…")
            return
        if tag in _BLOCK:
            self._break(1 if tag in ("li", "div") else 2)
            return
        if tag == "a" or tag in _INLINE:
            opened = self.stack.pop() if self.stack else ""
            if opened:
                self.out.append(f"</{opened}>")

    def handle_data(self, data: str) -> None:
        if self.skip or not data:
            return
        if not data.strip() and not self.out:
            return
        self._flush_break()
        self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            opened = self.stack.pop()
            if opened:
                self.out.append(f"</{opened}>")
        return "".join(self.out).strip()


def to_markup(source: str) -> str:
    """Mastodon-HTML → Pango-Markup."""
    conv = _Converter()
    conv.feed(source or "")
    conv.close()
    return conv.result()


def to_text(source: str) -> str:
    """Nur der sichtbare Text, etwa für Tooltips und Barrierefreiheit."""
    return html.unescape(re.sub(r"<[^>]+>", "", to_markup(source)))


def relative_time(iso: str, now: datetime | None = None) -> str:
    """Kurze Altersangabe: „jetzt“, „5 Min.“, „3 Std.“, „2 T.“ oder Datum."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    now = now or datetime.now(UTC)
    secs = max(0, int((now - dt).total_seconds()))
    if secs < 60:
        return _("now")
    if secs < 3600:
        return _("{n} min").format(n=secs // 60)
    if secs < 86400:
        return _("{n} h").format(n=secs // 3600)
    if secs < 7 * 86400:
        return _("{n} d").format(n=secs // 86400)
    local = dt.astimezone()
    return local.strftime("%d.%m.%Y") if local.year != now.astimezone().year else local.strftime("%d.%m.")
