# SPDX-License-Identifier: GPL-3.0-or-later
"""Zeichenzählung nach den Regeln der jeweiligen Plattform.

Mastodon (app/validators/status_length_validator.rb):
  - URLs zählen pauschal `characters_reserved_per_url` (Standard 23)
  - Mentions `@user@domain` zählen nur als `@user`
  - gezählt werden Grapheme, die Inhaltswarnung zählt mit

Bluesky (app.bsky.feed.post):
  - höchstens 300 Grapheme und 3000 Bytes UTF-8
  - die offizielle App kürzt URLs im sichtbaren Text, der volle Link steckt
    im Facet; wir machen es genauso (siehe `bluesky_shorten_url`)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .graphemes import count_graphemes

# Bewusst einfach gehalten: http(s)-URLs bis zum nächsten Leerraum, ohne
# abschließende Satzzeichen. Klammern bleiben, wenn sie ausgeglichen sind.
URL_RE = re.compile(r"(?<![\w@/])(https?://[^\s<>\"]+)", re.IGNORECASE)
_TRAILING = ".,:;!?'\"’”»"

MENTION_RE = re.compile(
    r"(?<![\w/@])@([a-z0-9_]+(?:[a-z0-9_.-]+[a-z0-9_]+)?)(@[a-z0-9.-]+\.[a-z0-9-]+)?",
    re.IGNORECASE,
)

HASHTAG_RE = re.compile(r"(?<![\w&#/])#([^\s#.,:;!?()\[\]{}<>\"'`]+)")


@dataclass(frozen=True)
class Span:
    start: int  # Codepunkt-Index
    end: int
    value: str


def _trim_url(url: str) -> str:
    while url and url[-1] in _TRAILING:
        url = url[:-1]
    if url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    return url


def find_urls(text: str) -> list[Span]:
    out = []
    for m in URL_RE.finditer(text):
        url = _trim_url(m.group(1))
        if len(url) > len("https://"):
            out.append(Span(m.start(1), m.start(1) + len(url), url))
    return out


def find_mentions(text: str) -> list[Span]:
    """Mentions im Fediverse-Stil (@user oder @user@domain)."""
    urls = find_urls(text)
    out = []
    for m in MENTION_RE.finditer(text):
        if any(u.start <= m.start() < u.end for u in urls):
            continue
        out.append(Span(m.start(), m.end(), m.group(0)))
    return out


def find_hashtags(text: str) -> list[Span]:
    urls = find_urls(text)
    out = []
    for m in HASHTAG_RE.finditer(text):
        tag = m.group(1).rstrip(_TRAILING)
        if not tag or tag.isdigit():
            continue
        if any(u.start <= m.start() < u.end for u in urls):
            continue
        out.append(Span(m.start(), m.start() + 1 + len(tag), "#" + tag))
    return out


# --------------------------------------------------------------------------
# Mastodon
# --------------------------------------------------------------------------

def mastodon_count(text: str, content_warning: str = "", url_length: int = 23) -> int:
    def repl_mention(m: re.Match[str]) -> str:
        return "@" + m.group(1)

    placeholder = "x" * url_length
    parts: list[str] = []
    last = 0
    for span in find_urls(text):
        parts.append(text[last:span.start])
        parts.append(placeholder)
        last = span.end
    parts.append(text[last:])
    rest = MENTION_RE.sub(repl_mention, "".join(parts))
    return count_graphemes(rest) + count_graphemes(content_warning)


# --------------------------------------------------------------------------
# Bluesky
# --------------------------------------------------------------------------

def bluesky_shorten_url(url: str) -> str:
    """Kurzform wie in der Bluesky-App: Host + Pfadanfang, sonst unverändert."""
    m = re.match(r"https?://(?:www\.)?([^/?#]+)(.*)", url, re.IGNORECASE)
    if not m:
        return url
    host, path = m.group(1), m.group(2)
    if path in ("", "/"):
        return host
    if len(path) > 15:
        return host + path[:13] + "..."
    return host + path


def bluesky_display_text(text: str) -> str:
    """Text so, wie er bei Bluesky gespeichert wird (URLs gekürzt)."""
    out: list[str] = []
    last = 0
    for span in find_urls(text):
        out.append(text[last:span.start])
        out.append(bluesky_shorten_url(span.value))
        last = span.end
    out.append(text[last:])
    return "".join(out)


def bluesky_count(text: str) -> tuple[int, int]:
    """(Grapheme, Bytes) des Bluesky-Texts nach dem Kürzen der URLs."""
    shown = bluesky_display_text(text)
    return count_graphemes(shown), len(shown.encode("utf-8"))


def generic_count(text: str) -> int:
    return count_graphemes(text)
