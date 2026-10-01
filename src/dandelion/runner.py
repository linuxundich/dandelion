# SPDX-License-Identifier: GPL-3.0-or-later
"""`dandelion --run-due`: kurzer Lauf ohne Fenster, gestartet vom systemd-Timer.

Läuft als eigene, nicht eindeutige GApplication neben einem eventuell
geöffneten Fenster. Doppelversand verhindert die Datenbank (claim_post).
Aktionen aus Benachrichtigungen landen per D-Bus-Aktivierung in der
eigentlichen Anwendung.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from gi.repository import Gio

from .core.publisher import Publisher
from .core.scheduler import MissedPolicy, Scheduler
from .core.secrets import LibsecretStore
from .core.store import Store
from .core.trigger import SystemdTrigger, in_flatpak
from .net.http import SoupHttpClient
from .notify import notify_result
from .platforms import Registry
from .util import spawn

log = logging.getLogger(__name__)


def make_scheduler(store: Store, publisher: Publisher, settings: Gio.Settings) -> Scheduler:
    return Scheduler(store, publisher,
                     policy=MissedPolicy(settings.get_string("missed-policy")),
                     grace=timedelta(minutes=settings.get_int("missed-grace-minutes")))


class Runner(Gio.Application):
    def __init__(self, app_id: str) -> None:
        super().__init__(application_id=app_id, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.exit_code = 0

    def do_activate(self) -> None:
        self.hold()
        spawn(self._run(), on_error=self._failed)

    async def _run(self) -> None:
        store: Store | None = None
        try:
            settings = Gio.Settings.new(self.get_application_id())
            store = Store()
            http = SoupHttpClient()
            registry = Registry(http, LibsecretStore())
            scheduler = make_scheduler(store, Publisher(store, registry), settings)
            result = await scheduler.run_due()
            log.info("Geplante Beiträge: %d gesendet, %d verspätet, %d verpasst",
                     len(result.sent), len(result.late), len(result.missed))
            notify_result(self, settings, result)
            if not in_flatpak():
                await SystemdTrigger().update(result.next_due)
        finally:
            if store:
                store.close()
            self.release()

    def _failed(self, exc: BaseException) -> None:
        log.error("Lauf des Schedulers fehlgeschlagen", exc_info=exc)
        self.exit_code = 1


def run_due(app_id: str) -> int:
    runner = Runner(app_id)
    code = runner.run([])
    return code or runner.exit_code
