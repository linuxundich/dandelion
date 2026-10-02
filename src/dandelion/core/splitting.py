# SPDX-License-Identifier: GPL-3.0-or-later
"""Aufteilen langer Texte in Threads.

Getrennt wird bevorzugt an Absätzen, dann an Satzenden, zuletzt an
Wortgrenzen; URLs werden nie zerteilt. Eine Zeile, die nur `---` enthält,
setzt eine Trennstelle von Hand. Gezählt wird mit der Zählfunktion der
jeweiligen Plattform, damit URL-Gewichte und Emoji stimmen.
"""

from __future__ import annotations

import re
from collections.abc import Callable

#: Werte von Post.thread_mode
THREAD_OFF = "off"
NUMBERING = {
    "plain": "",
    "fraction": "{i}/{n}",
    "thread-fraction": "🧵 {i}/{n}",
}

MANUAL_SEPARATOR = re.compile(r"^[ \t]*---[ \t]*$", re.MULTILINE)
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")

Counter = Callable[[str], int]


def has_manual_breaks(text: str) -> bool:
    return bool(MANUAL_SEPARATOR.search(text))


def _label(style: str, i: int, n: int) -> str:
    template = NUMBERING.get(style, "")
    return template.format(i=i, n=n) if template else ""


def _pack(units: list[str], joiner: str, count: Counter, cap: int) -> list[str]:
    """Fasst Einheiten gierig zu Teilen zusammen, die höchstens `cap` lang sind."""
    parts: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}{joiner}{unit}" if current else unit
        if count(candidate) <= cap:
            current = candidate
            continue
        if current:
            parts.append(current)
        current = unit
    if current:
        parts.append(current)
    return parts


def _split_words(text: str, count: Counter, cap: int) -> list[str]:
    words = text.split()
    parts = _pack(words, " ", count, cap)
    out: list[str] = []
    for part in parts:
        if count(part) <= cap or " " in part:
            out.append(part)
            continue
        # Ein einzelnes Wort (keine URL) ist länger als der Platz: hart teilen
        if part.startswith(("http://", "https://")):
            out.append(part)
            continue
        chunk = ""
        for ch in part:
            if chunk and count(chunk + ch) > cap:
                out.append(chunk)
                chunk = ""
            chunk += ch
        if chunk:
            out.append(chunk)
    return out


def _split_block(text: str, count: Counter, cap: int) -> list[str]:
    """Teilt einen Block ohne manuelle Trennstellen."""
    if count(text) <= cap:
        return [text]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units: list[str] = []
    for para in paragraphs:
        if count(para) <= cap:
            units.append(para)
            continue
        sentences = [s for s in _SENTENCE_END.split(para) if s]
        for sentence in sentences:
            if count(sentence) <= cap:
                units.append(sentence)
            else:
                units.extend(_split_words(sentence, count, cap))
    # Absätze mit Leerzeile verbinden, Sätze desselben Absatzes mit Leerzeichen
    parts: list[str] = []
    current = ""
    for unit in units:
        joiner = "\n\n" if unit in paragraphs else " "
        candidate = f"{current}{joiner}{unit}" if current else unit
        if count(candidate) <= cap:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = unit
    if current:
        parts.append(current)
    return parts


def split_thread(text: str, count: Counter, limit: int, style: str = "fraction") -> list[str]:
    """Liefert die Teile eines Threads (ein Teil, wenn nichts zu teilen ist)."""
    text = text.strip()
    blocks = [b.strip() for b in MANUAL_SEPARATOR.split(text) if b.strip()]
    if len(blocks) <= 1 and count(text) <= limit:
        return [MANUAL_SEPARATOR.sub("", text).strip()] if text else [text]

    n_guess = max(2, len(blocks))
    parts: list[str] = []
    for _attempt in range(6):
        reserve = count(" " + _label(style, n_guess, n_guess)) if NUMBERING.get(style) else 0
        cap = max(10, limit - reserve)
        parts = []
        for block in blocks or [text]:
            parts.extend(_split_block(block, count, cap))
        if len(parts) == n_guess or not NUMBERING.get(style):
            break
        n_guess = len(parts)

    n = len(parts)
    if n <= 1:
        return parts or [text]
    if NUMBERING.get(style):
        parts = [f"{p.rstrip()} {_label(style, i, n)}" for i, p in enumerate(parts, 1)]
    return parts
