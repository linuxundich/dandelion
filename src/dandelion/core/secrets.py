# SPDX-License-Identifier: GPL-3.0-or-later
"""Zugangsdaten im Secret Service (GNOME Schlüsselbund) über libsecret.

Pro Profil und Art (`oauth`, `app-password`, `client-credentials`,
`api-key`) gibt es einen Eintrag mit JSON-Inhalt. Nichts davon landet in
der Datenbank, in GSettings oder im Log.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol

SCHEMA_NAME = "de.linuxundich.Dandelion.Credential"


class SecretStore(Protocol):
    async def get(self, owner: str, kind: str) -> dict[str, Any] | None: ...
    async def set(self, owner: str, kind: str, label: str, data: dict[str, Any]) -> None: ...
    async def delete(self, owner: str, kind: str | None = None) -> None: ...


class MemorySecretStore:
    """Für Tests."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    async def get(self, owner: str, kind: str) -> dict[str, Any] | None:
        return self.items.get((owner, kind))

    async def set(self, owner: str, kind: str, label: str, data: dict[str, Any]) -> None:
        self.items[(owner, kind)] = dict(data)

    async def delete(self, owner: str, kind: str | None = None) -> None:
        for key in [k for k in self.items if k[0] == owner and (kind is None or k[1] == kind)]:
            del self.items[key]


class LibsecretStore:
    def __init__(self) -> None:
        import gi
        gi.require_version("Secret", "1")
        from gi.repository import Secret
        self._Secret = Secret
        self.schema = Secret.Schema.new(
            SCHEMA_NAME, Secret.SchemaFlags.NONE,
            {"profile": Secret.SchemaAttributeType.STRING,
             "kind": Secret.SchemaAttributeType.STRING})

    @staticmethod
    def _call(start: Any, finish: Any, *args: Any) -> asyncio.Future[Any]:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Any] = loop.create_future()

        def done(_src: Any, result: Any, *_: Any) -> None:
            if fut.cancelled():
                return
            try:
                fut.set_result(finish(result))
            except Exception as e:  # GLib.Error
                fut.set_exception(e)

        start(*args, None, done)
        return fut

    async def get(self, owner: str, kind: str) -> dict[str, Any] | None:
        S = self._Secret
        value = await self._call(S.password_lookup, S.password_lookup_finish,
                                 self.schema, {"profile": owner, "kind": kind})
        return json.loads(value) if value else None

    async def set(self, owner: str, kind: str, label: str, data: dict[str, Any]) -> None:
        S = self._Secret
        await self._call(S.password_store, S.password_store_finish,
                         self.schema, {"profile": owner, "kind": kind},
                         S.COLLECTION_DEFAULT, label, json.dumps(data))

    async def delete(self, owner: str, kind: str | None = None) -> None:
        S = self._Secret
        attrs = {"profile": owner}
        if kind:
            attrs["kind"] = kind
        while True:
            removed = await self._call(S.password_clear, S.password_clear_finish,
                                       self.schema, attrs)
            if not removed:
                break
