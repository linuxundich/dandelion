# SPDX-License-Identifier: GPL-3.0-or-later
"""OAuth-Hilfen: PKCE und ein kurzlebiger Loopback-Server auf 127.0.0.1."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import urllib.parse
from dataclasses import dataclass
from gettext import gettext as _


@dataclass
class Pkce:
    verifier: str
    challenge: str
    method: str = "S256"

    @classmethod
    def create(cls) -> Pkce:
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return cls(verifier, challenge)


def new_state() -> str:
    return secrets.token_urlsafe(24)


class OAuthError(Exception):
    pass


_SUCCESS_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Dandelion</title><style>
body{{font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0;
background:#fafafb;color:#222}}@media(prefers-color-scheme:dark){{body{{background:#222226;color:#eee}}}}
main{{text-align:center;max-width:28em;padding:1em}}</style></head>
<body><main><h1>{title}</h1><p>{text}</p></main></body></html>"""


class LoopbackServer:
    """Wartet auf genau einen Redirect `http://127.0.0.1:PORT/callback?…`."""

    def __init__(self) -> None:
        import gi
        gi.require_version("Soup", "3.0")
        from gi.repository import Soup
        self._Soup = Soup
        self.server = Soup.Server()
        self._future: asyncio.Future[dict[str, str]] | None = None
        self.port = 0

    def start(self, port: int = 0, host: str = "127.0.0.1") -> str:
        """Startet den Server. Mit festem `port` (für Plattformen, die die
        Redirect-Adresse exakt registriert verlangen) auf IPv4 und IPv6,
        damit auch „localhost“ funktioniert, das Browser oft als ::1 auflösen."""
        Soup = self._Soup
        self._future = asyncio.get_running_loop().create_future()
        self.server.add_handler("/callback", self._handle)
        try:
            if port:
                self.server.listen_local(port, 0)
            else:
                self.server.listen_local(0, Soup.ServerListenOptions.IPV4_ONLY)
        except Exception as e:  # GLib.Error: Port belegt
            raise OAuthError(_("Port {port} is already in use. Close the other program and "
                               "try again.").format(port=port)) from e
        self.port = self.server.get_uris()[0].get_port()
        return f"http://{host}:{self.port}/callback"

    def _handle(self, server, msg, path, query, *args):  # type: ignore[no-untyped-def]
        params = dict(query) if query else {}
        uri = msg.get_uri()
        if not params and uri.get_query():
            params = dict(urllib.parse.parse_qsl(uri.get_query()))
        ok = "code" in params
        title = _("Signed in") if ok else _("Sign-in failed")
        text = (_("You can close this tab and return to Dandelion.") if ok
                else _("Return to Dandelion and try again."))
        body = _SUCCESS_PAGE.format(title=title, text=text).encode("utf-8")
        msg.set_status(200, None)
        msg.set_response("text/html; charset=utf-8", self._Soup.MemoryUse.COPY, body)
        if self._future and not self._future.done():
            self._future.set_result(params)

    async def wait(self, timeout: float = 600) -> dict[str, str]:
        assert self._future is not None
        try:
            return await asyncio.wait_for(self._future, timeout)
        finally:
            self.stop()

    def stop(self) -> None:
        self.server.disconnect()
        if self._future and not self._future.done():
            self._future.cancel()


def parse_code_input(text: str) -> dict[str, str]:
    """Akzeptiert einen eingefügten Code oder die komplette Redirect-URL."""
    text = text.strip()
    if "?" in text and "code=" in text:
        return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(text).query))
    return {"code": text}
