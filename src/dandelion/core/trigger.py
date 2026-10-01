# SPDX-License-Identifier: GPL-3.0-or-later
"""Auslöser für den Hintergrunddienst.

Nativ (AUR, Meson): systemd-User-Timer `dandelion-scheduler.timer`, dessen
`OnCalendar` per Drop-in immer auf den nächsten Termin zeigt. Zwischen zwei
Terminen läuft kein Prozess; Suspend und Neustart holt systemd nach
(`Persistent=true`, `OnStartupSec`).

Flatpak: Background-Portal mit Autostart, Dandelion läuft dann ohne Fenster
(`--background`) und prüft selbst, solange etwas geplant ist.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path

from gi.repository import Gio, GLib

log = logging.getLogger(__name__)

TIMER = "dandelion-scheduler.timer"
SERVICE = "dandelion-scheduler.service"
_PASS_ENV = ("GSETTINGS_SCHEMA_DIR", "XDG_DATA_HOME", "XDG_CACHE_HOME", "GSETTINGS_BACKEND",
             "LANGUAGE", "DANDELION_DEBUG")


def in_flatpak() -> bool:
    return os.path.exists("/.flatpak-info")


def unit_dir() -> Path:
    return Path(GLib.get_user_config_dir()) / "systemd" / "user"


def dropin_path() -> Path:
    return unit_dir() / f"{TIMER}.d" / "next.conf"


def calendar_spec(when: datetime) -> str:
    """OnCalendar-Wert für einen Zeitpunkt, immer in UTC (eindeutig bei Zeitumstellung)."""
    return when.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def dropin_text(when: datetime) -> str:
    return (
        "# Von Dandelion verwaltet: nächster geplanter Beitrag\n"
        "[Timer]\n"
        "OnCalendar=\n"
        f"OnCalendar={calendar_spec(when)}\n"
    )


def service_text(executable: str, env: dict[str, str]) -> str:
    lines = [
        "# Von Dandelion erzeugt",
        "[Unit]",
        "Description=Dandelion: geplante Beiträge senden",
        "After=network-online.target",
        "",
        "[Service]",
        "Type=oneshot",
        f"ExecStart={shlex.quote(executable)} --run-due",
    ]
    for key, value in sorted(env.items()):
        lines.append(f"Environment={key}={value}")
    return "\n".join(lines) + "\n"


TIMER_TEXT = """# Von Dandelion erzeugt
[Unit]
Description=Dandelion: nächster geplanter Beitrag

[Timer]
OnStartupSec=2min
Persistent=true
AccuracySec=5s
WakeSystem=false

[Install]
WantedBy=timers.target
"""


class SystemdTrigger:
    """Steuert den User-Timer über die D-Bus-Schnittstelle von systemd."""

    kind = "systemd"

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or os.path.abspath(sys.argv[0])
        self._proxy: Gio.DBusProxy | None = None

    def _manager(self) -> Gio.DBusProxy:
        if self._proxy is None:
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES, None,
                "org.freedesktop.systemd1", "/org/freedesktop/systemd1",
                "org.freedesktop.systemd1.Manager", None)
        return self._proxy

    async def _call(self, method: str, params: GLib.Variant | None) -> GLib.Variant:
        proxy = self._manager()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[GLib.Variant] = loop.create_future()

        def done(p: Gio.DBusProxy, res: Gio.AsyncResult) -> None:
            try:
                fut.set_result(p.call_finish(res))
            except GLib.Error as e:
                fut.set_exception(e)

        proxy.call(method, params, Gio.DBusCallFlags.NONE, 10_000, None, done)
        return await fut

    async def available(self) -> bool:
        try:
            await self._call("GetUnitFileState", GLib.Variant("(s)", ("basic.target",)))
            return True
        except GLib.Error:
            return False

    async def _ensure_units(self) -> None:
        """Nutzt mitgelieferte Units, sonst werden sie im Benutzerverzeichnis angelegt."""
        packaged = True
        try:
            await self._call("GetUnitFileState", GLib.Variant("(s)", (TIMER,)))
        except GLib.Error:
            packaged = False
        own = unit_dir() / SERVICE
        if packaged and not own.exists():
            return
        env = {k: os.environ[k] for k in _PASS_ENV if os.environ.get(k)}
        unit_dir().mkdir(parents=True, exist_ok=True)
        own.write_text(service_text(self.executable, env), encoding="utf-8")
        (unit_dir() / TIMER).write_text(TIMER_TEXT, encoding="utf-8")
        await self._call("Reload", None)

    async def is_active(self) -> bool:
        try:
            res = await self._call("ListUnitsByNames", GLib.Variant("(as)", ([TIMER],)))
        except GLib.Error:
            return False
        units = res.unpack()[0]
        return bool(units) and units[0][3] == "active"

    async def enable(self) -> None:
        await self._ensure_units()
        await self._call("EnableUnitFiles", GLib.Variant("(asbb)", ([TIMER], False, True)))
        await self._call("Reload", None)
        await self._call("StartUnit", GLib.Variant("(ss)", (TIMER, "replace")))
        log.info("Hintergrunddienst aktiviert")

    async def disable(self) -> None:
        try:
            await self._call("StopUnit", GLib.Variant("(ss)", (TIMER, "replace")))
            await self._call("DisableUnitFiles", GLib.Variant("(asb)", ([TIMER], False)))
        except GLib.Error as e:
            log.info("Timer ließ sich nicht deaktivieren: %s", e.message)
        dropin_path().unlink(missing_ok=True)
        await self._call("Reload", None)

    async def update(self, next_due: datetime | None) -> None:
        """Stellt den Timer auf den nächsten Termin (oder entfernt den Termin)."""
        path = dropin_path()
        text = dropin_text(next_due) if next_due else None
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if text == current:
            return
        if text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        if not await self.is_active():
            return
        await self._call("Reload", None)
        await self._call("RestartUnit", GLib.Variant("(ss)", (TIMER, "replace")))
        log.debug("Timer gestellt auf %s", calendar_spec(next_due) if next_due else "–")


class PortalTrigger:
    """Flatpak: Autostart über das Background-Portal, Weckzeit hält der Prozess selbst."""

    kind = "portal"

    def __init__(self) -> None:
        self._active = False

    async def available(self) -> bool:
        return True

    async def is_active(self) -> bool:
        return self._active

    def request(self, window, on_done) -> None:  # type: ignore[no-untyped-def]
        """Fragt das Portal (mit Fenster als Elternteil) nach Hintergrundrechten."""
        import gi
        gi.require_version("Xdp", "1.0")
        gi.require_version("XdpGtk4", "1.0")
        from gi.repository import Xdp, XdpGtk4

        portal = Xdp.Portal()
        parent = XdpGtk4.parent_new_gtk(window) if window else None

        def finished(p, result) -> None:  # type: ignore[no-untyped-def]
            try:
                self._active = p.request_background_finish(result)
            except GLib.Error as e:
                log.info("Background-Portal: %s", e.message)
                self._active = False
            on_done(self._active)

        portal.request_background(
            parent, _reason(), ["dandelion", "--background"],
            Xdp.BackgroundFlags.AUTOSTART, None, finished)

    async def enable(self) -> None:
        self._active = True

    async def disable(self) -> None:
        self._active = False

    async def update(self, next_due: datetime | None) -> None:
        return None


def _reason() -> str:
    from gettext import gettext as _
    return _("Dandelion publishes scheduled posts even when its window is closed.")


def create_trigger() -> SystemdTrigger | PortalTrigger:
    return PortalTrigger() if in_flatpak() else SystemdTrigger()
