# SPDX-License-Identifier: GPL-3.0-or-later
"""Link-Vorschau aus Open-Graph-Daten einer Webseite."""

from __future__ import annotations

import html
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser

from .http import HttpClient, NetworkError, Request

MAX_HTML = 1_500_000
MAX_IMAGE = 8_000_000


@dataclass
class LinkCard:
    url: str
    title: str = ""
    description: str = ""
    image_url: str | None = None
    site: str = ""
    image_data: bytes | None = None
    image_mime: str | None = None


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"]
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()


def parse_html(url: str, text: str) -> LinkCard:
    p = _MetaParser()
    try:
        p.feed(text)
    except Exception:  # kaputtes HTML: nehmen, was bis dahin da ist
        pass
    m = p.meta
    image = m.get("og:image") or m.get("og:image:url") or m.get("twitter:image")
    if image:
        image = urllib.parse.urljoin(url, html.unescape(image))
    return LinkCard(
        url=url,
        title=(m.get("og:title") or m.get("twitter:title") or p.title or "").strip()[:300],
        description=(m.get("og:description") or m.get("twitter:description")
                     or m.get("description") or "").strip()[:1000],
        image_url=image,
        site=m.get("og:site_name") or urllib.parse.urlsplit(url).hostname or "",
    )


async def fetch_card(http: HttpClient, url: str, with_image: bool = True) -> LinkCard | None:
    try:
        resp = await http.send(Request("GET", url, headers={"Accept": "text/html"}, timeout=15))
    except NetworkError:
        return None
    if not resp.ok or "html" not in resp.headers.get("content-type", "text/html"):
        return None
    card = parse_html(resp.url or url, resp.body[:MAX_HTML].decode("utf-8", errors="replace"))
    if with_image and card.image_url:
        try:
            img = await http.send(Request("GET", card.image_url, headers={"Accept": "image/*"},
                                          timeout=20))
            if img.ok and len(img.body) <= MAX_IMAGE:
                card.image_data = img.body
                card.image_mime = img.headers.get("content-type", "image/jpeg").split(";")[0]
        except NetworkError:
            pass
    return card
