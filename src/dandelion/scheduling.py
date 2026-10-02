# SPDX-License-Identifier: GPL-3.0-or-later
"""Planung in der laufenden Anwendung: Ticker, Hintergrunddienst, Meldungen.

Solange Dandelion läuft (mit Fenster oder unter Flatpak im Hintergrund),
prüft ein Ticker alle 30 Sekunden auf fällige Beiträge. Ist das Fenster zu,
übernimmt nativ der systemd-Timer (`dandelion --run-due`).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from gi.repository import GLib, GObject

from .core.scheduler import RunResult
from .core.trigger import PortalTrigger, create_trigger
from .notify import notify_result
from .runner import make_scheduler
from .util import spawn

if TYPE_CHECKING:
    from .application import DandelionApplication

log = logging.getLogger(__name__)
TICK_SECONDS = 30


class SchedulingService(GObject.Object):
    __gsignals__ = {
        # Geplante Beiträge haben sich geändert (gesendet, verpasst, neu geplant)
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # Verpasste Beiträge gefunden, während ein Fenster offen ist
        "missed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    active = GObject.Property(type=bool, default=False)
    available = GObject.Property(type=bool, default=False)

    def __init__(self, app: DandelionApplication) -> None:
        super().__init__()
        self.app = app
        self.trigger = create_trigger()
        self._source = 0
        self._running = False
        self._remote_source = 0
        self._remote_running = False
        self._remote_again = False

    @property
    def is_portal(self) -> bool:
        return isinstance(self.trigger, PortalTrigger)

    def start(self) -> None:
        spawn(self._init())
        self._source = GLib.timeout_add_seconds(TICK_SECONDS, self._tick)
        # Einmal sofort prüfen; _tick() selbst bleibt aktiv, darf also nicht
        # direkt als Idle-Quelle laufen (sonst Dauerschleife mit 100 % CPU)
        GLib.idle_add(self._first_tick)

    def stop(self) -> None:
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0

    async def _init(self) -> None:
        self.props.available = await self.trigger.available()
        self.props.active = await self.trigger.is_active()

    def _first_tick(self) -> bool:
        self._tick()
        return GLib.SOURCE_REMOVE

    def _tick(self) -> bool:
        if not self._running:
            spawn(self.run_due())
        return GLib.SOURCE_CONTINUE

    def scheduler(self):  # type: ignore[no-untyped-def]
        return make_scheduler(self.app.store, self.app.publisher, self.app.settings)

    async def run_due(self) -> RunResult:
        self._running = True
        try:
            result = await self.scheduler().run_due()
        finally:
            self._running = False
        if result.sent or result.late or result.missed:
            has_window = self.app.props.active_window is not None
            if result.missed and has_window:
                self.emit("missed")
                missed, result.missed = result.missed, []
                notify_result(self.app, self.app.settings, result)
                result.missed = missed
            else:
                notify_result(self.app, self.app.settings, result)
            self.emit("changed")
        await self._update_trigger(result.next_due)
        self.app.on_scheduler_idle(result.next_due)
        return result

    async def _update_trigger(self, next_due: datetime | None) -> None:
        try:
            await self.trigger.update(next_due)
        except GLib.Error as e:
            log.warning("Timer konnte nicht gestellt werden: %s", e.message)

    def schedule_changed(self) -> None:
        """Nach dem Planen, Verschieben, Pausieren oder Löschen aufrufen."""
        spawn(self._update_trigger(self.scheduler().next_due()))
        self.emit("changed")
        self._queue_remote_sync()

    # -- Serverseitiges Planen (Mastodon) -------------------------------------
    def _queue_remote_sync(self, delay: int = 3) -> None:
        """Gleicht nach kurzer Ruhepause mit den Servern ab (nicht bei jedem Tastendruck)."""
        if self._remote_source:
            GLib.source_remove(self._remote_source)
        self._remote_source = GLib.timeout_add_seconds(delay, self._run_remote_sync)

    def _run_remote_sync(self) -> bool:
        self._remote_source = 0
        if self._remote_running:
            self._remote_again = True
            return GLib.SOURCE_REMOVE
        spawn(self._remote_sync())
        return GLib.SOURCE_REMOVE

    async def _remote_sync(self) -> None:
        from .core.remote_schedule import RemoteScheduler
        self._remote_running = True
        try:
            remote = RemoteScheduler(self.app.store, self.app.registry, self.app.publisher)
            errors = await remote.sync_all()
        finally:
            self._remote_running = False
        if errors:
            win = self.app.props.active_window
            if win and hasattr(win, "toast"):
                from gettext import gettext as _
                win.toast(_("Scheduling on the server failed, Dandelion sends the post "
                            "itself: {error}").format(error=errors[0]), timeout=10)
        self.emit("changed")
        if self._remote_again:
            self._remote_again = False
            self._queue_remote_sync(1)

    def enable(self, window=None) -> None:  # type: ignore[no-untyped-def]
        if isinstance(self.trigger, PortalTrigger):
            self.trigger.request(window, lambda ok: self.set_property("active", ok))
            return

        async def run() -> None:
            await self.trigger.enable()
            await self.trigger.update(self.scheduler().next_due())
            self.props.active = await self.trigger.is_active()

        spawn(run(), on_error=lambda e: log.warning("Hintergrunddienst: %s", e))

    def disable(self) -> None:
        async def run() -> None:
            await self.trigger.disable()
            self.props.active = await self.trigger.is_active()

        spawn(run(), on_error=lambda e: log.warning("Hintergrunddienst: %s", e))
