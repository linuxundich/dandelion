# SPDX-License-Identifier: GPL-3.0-or-later
"""Lädt Profilbilder einmal herunter und legt sie im Cache ab."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from gi.repository import Adw, Gdk, GLib

from ..core.store import cache_dir
from ..net.http import HttpClient, NetworkError, Request
from ..util import spawn

log = logging.getLogger(__name__)


class AvatarCache:
    def __init__(self, http: HttpClient) -> None:
        self.http = http
        self.dir = cache_dir() / "avatars"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._textures: dict[str, Gdk.Texture] = {}
        self._waiting: dict[str, list[Adw.Avatar]] = {}

    def _path(self, url: str) -> Path:
        return self.dir / hashlib.sha1(url.encode()).hexdigest()

    def apply(self, avatar: Adw.Avatar, url: str | None) -> None:
        if not url:
            return
        tex = self._textures.get(url)
        if tex is None and self._path(url).exists():
            tex = self._load(url)
        if tex is not None:
            avatar.set_custom_image(tex)
            return
        if url in self._waiting:
            self._waiting[url].append(avatar)
            return
        self._waiting[url] = [avatar]
        spawn(self._download(url))

    def _load(self, url: str) -> Gdk.Texture | None:
        try:
            tex = Gdk.Texture.new_from_filename(str(self._path(url)))
        except GLib.Error:
            return None
        self._textures[url] = tex
        return tex

    async def _download(self, url: str) -> None:
        try:
            resp = await self.http.send(Request("GET", url, headers={"Accept": "image/*"}))
            if resp.ok and resp.body:
                self._path(url).write_bytes(resp.body)
        except NetworkError as e:
            log.debug("Avatar nicht geladen: %s", e)
        tex = self._load(url) if self._path(url).exists() else None
        for avatar in self._waiting.pop(url, []):
            if tex is not None:
                avatar.set_custom_image(tex)
