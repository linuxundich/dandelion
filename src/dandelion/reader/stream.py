# SPDX-License-Identifier: GPL-3.0-or-later
"""Live-Verbindung zu Mastodon (WebSocket, libsoup 3).

Ein `user`-Stream liefert neue Beiträge, Änderungen, Löschungen und
Benachrichtigungen. Bricht die Verbindung ab, versucht es der Stream mit
wachsendem Abstand erneut und meldet nach jedem Aufbau `None`, damit die
Oberfläche nachlädt, was in der Zwischenzeit passiert ist.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..core.models import Profile
from ..net.http import NetworkError, Request
from ..platforms.base import PlatformError
from ..platforms.mastodon import Mastodon

if TYPE_CHECKING:
    from ..net.http import SoupHttpClient
    from .service import ReaderService

log = logging.getLogger(__name__)

MIN_DELAY = 2
MAX_DELAY = 120
STABLE_AFTER = 20          # so lange muss eine Verbindung halten, damit der Abstand zurückgesetzt wird
KEEPALIVE = 30


class MastodonStream:
    def __init__(self, http: SoupHttpClient, platform: Mastodon, service: ReaderService,
                 profile: Profile, callback: Callable[[Profile, str | None], None]) -> None:
        self.http, self.platform, self.service = http, platform, service
        self.profile, self.callback = profile, callback
        self.connected = False
        self._task: asyncio.Task | None = None
        self._conn = None
        self._cancel = None

    # -- Steuerung ----------------------------------------------------------
    def start(self) -> None:
        from ..util import spawn
        self._task = spawn(self._run())

    def stop(self) -> None:
        self.connected = False
        if self._cancel is not None:
            self._cancel.cancel()
        if self._conn is not None:
            try:
                self._conn.close(1000, None)
            except Exception:                                  # bereits geschlossen
                pass
        if self._task is not None:
            self._task.cancel()
        self._task = None

    # -- Adresse ------------------------------------------------------------
    async def stream_url(self) -> str:
        """Adresse des Streaming-Servers; viele Instanzen betreiben ihn unter anderem Namen."""
        base = f"wss://{self.profile.server}"
        try:
            resp = await self.http.send(Request("GET", f"https://{self.profile.server}/api/v2/instance"))
            url = ((resp.json() or {}).get("configuration", {}).get("urls", {}) or {}).get("streaming")
            if url:
                base = url.rstrip("/")
        except (NetworkError, ValueError):
            pass
        return f"{base}/api/v1/streaming?stream=user"

    # -- Schleife -----------------------------------------------------------
    async def _run(self) -> None:
        delay = MIN_DELAY
        while True:
            started = time.monotonic()
            try:
                await self._session()
            except asyncio.CancelledError:
                raise
            except (NetworkError, PlatformError) as e:
                log.info("Stream %s: %s", self.profile.full_handle, e)
            except Exception:
                log.exception("Stream %s abgebrochen", self.profile.full_handle)
            self.connected = False
            if time.monotonic() - started > STABLE_AFTER:
                delay = MIN_DELAY
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_DELAY)

    async def _session(self) -> None:
        from gi.repository import GLib, Gio, Soup
        token = await self.platform._token(self.profile)
        url = await self.stream_url()
        msg = Soup.Message.new("GET", url)
        if msg is None:
            raise NetworkError("invalid stream address")
        msg.get_request_headers().replace("Authorization", f"Bearer {token}")
        loop = asyncio.get_running_loop()
        self._cancel = Gio.Cancellable()
        opened: asyncio.Future = loop.create_future()

        def done(session, result) -> None:  # type: ignore[no-untyped-def]
            try:
                opened.set_result(session.websocket_connect_finish(result))
            except GLib.Error as e:
                opened.set_exception(NetworkError(e.message))

        self.http.session.websocket_connect_async(msg, None, None, GLib.PRIORITY_DEFAULT,
                                                  self._cancel, done)
        conn = await opened
        self._conn = conn
        conn.set_keepalive_interval(KEEPALIVE)
        closed: asyncio.Future = loop.create_future()
        conn.connect("message", self._on_message)
        conn.connect("closed", lambda *_a: closed.done() or closed.set_result(None))
        conn.connect("error", lambda _c, err: log.info("Stream-Fehler: %s", err.message))
        self.connected = True
        log.info("Stream %s verbunden", self.profile.full_handle)
        self.callback(self.profile, None)               # nachladen, was inzwischen fehlt
        try:
            await closed
        finally:
            self._conn = None

    def _on_message(self, _conn, kind, data) -> None:  # type: ignore[no-untyped-def]
        from gi.repository import Soup
        if kind != Soup.WebsocketDataType.TEXT:
            return
        try:
            event = json.loads(bytes(data.get_data()).decode("utf-8"))
        except ValueError:
            return
        feed = self.service.handle_stream_event(self.profile, event)
        if feed:
            self.callback(self.profile, feed)
