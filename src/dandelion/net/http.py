# SPDX-License-Identifier: GPL-3.0-or-later
"""Schlanke HTTP-Schicht über libsoup3 mit asyncio.

Plattform-Backends sprechen nur mit dem Protokoll `HttpClient`. In Tests
wird eine Attrappe eingesetzt, in der App `SoupHttpClient`.

Geloggt werden Methode, Host, Pfad und Status, aber nie Header, Bodys oder
sensible Query-Parameter.
"""

from __future__ import annotations

import json as _json
import logging
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger(__name__)

USER_AGENT = "Dandelion/0.1 (+https://github.com/linuxundich/dandelion)"
_SENSITIVE_PARAMS = {"code", "access_token", "refresh_token", "client_secret", "password",
                     "code_verifier", "token"}


class NetworkError(Exception):
    """Keine Antwort erhalten (DNS, Verbindung, Zeitüberschreitung)."""


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes
    url: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        if not self.body:
            return None
        return _json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass
class FilePart:
    name: str
    filename: str
    content_type: str
    data: bytes


@dataclass
class Request:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: Mapping[str, Any] | None = None
    json: Any = None
    form: Mapping[str, Any] | None = None
    data: bytes | None = None
    content_type: str | None = None
    files: list[FilePart] | None = None
    timeout: int = 30

    def full_url(self) -> str:
        if not self.params:
            return self.url
        sep = "&" if "?" in self.url else "?"
        return self.url + sep + urllib.parse.urlencode(_flatten(self.params), doseq=True)


def _flatten(values: Mapping[str, Any]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k, v in values.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            out.extend((k, str(x)) for x in v)
        elif isinstance(v, bool):
            out.append((k, "true" if v else "false"))
        else:
            out.append((k, str(v)))
    return out


def redact_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    safe = [(k, "***" if k.lower() in _SENSITIVE_PARAMS else v) for k, v in query]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(safe)))


class HttpClient(Protocol):
    async def send(self, request: Request) -> Response: ...


async def request(client: HttpClient, method: str, url: str, **kwargs: Any) -> Response:
    return await client.send(Request(method, url, **kwargs))


class SoupHttpClient:
    """HttpClient auf Basis von libsoup3, nutzt die Proxy-Einstellungen des Systems."""

    def __init__(self) -> None:
        import gi
        gi.require_version("Soup", "3.0")
        from gi.repository import Soup
        self._Soup = Soup
        self.session = Soup.Session(user_agent=USER_AGENT, timeout=60)

    async def send(self, req: Request) -> Response:
        from gi.repository import GLib
        Soup = self._Soup
        url = req.full_url()

        if req.files:
            multipart = Soup.Multipart.new("multipart/form-data")
            for k, v in _flatten(req.form or {}):
                multipart.append_form_string(k, v)
            for f in req.files:
                multipart.append_form_file(f.name, f.filename, f.content_type,
                                           GLib.Bytes.new(f.data))
            msg = Soup.Message.new_from_multipart(url, multipart)
            msg.set_method(req.method)
        else:
            msg = Soup.Message.new(req.method, url)
            if msg is None:
                raise NetworkError(f"Ungültige Adresse: {redact_url(url)}")
            body: bytes | None = None
            ctype = req.content_type
            if req.json is not None:
                body = _json.dumps(req.json, ensure_ascii=False).encode("utf-8")
                ctype = "application/json"
            elif req.form is not None:
                body = urllib.parse.urlencode(_flatten(req.form), doseq=True).encode("ascii")
                ctype = "application/x-www-form-urlencoded"
            elif req.data is not None:
                body = req.data
            if body is not None:
                msg.set_request_body_from_bytes(ctype or "application/octet-stream",
                                                GLib.Bytes.new(body))
        headers = msg.get_request_headers()
        headers.replace("Accept", "application/json")
        for k, v in req.headers.items():
            headers.replace(k, v)

        try:
            data = await self.session.send_and_read_async(msg, GLib.PRIORITY_DEFAULT, None)
        except GLib.Error as e:
            log.info("%s %s → Fehler: %s", req.method, redact_url(url), e.message)
            raise NetworkError(e.message) from e

        resp_headers: dict[str, str] = {}
        msg.get_response_headers().foreach(lambda k, v: resp_headers.__setitem__(k.lower(), v))
        status = msg.get_status()
        log.debug("%s %s → %s", req.method, redact_url(url), status)
        return Response(int(status), resp_headers, bytes(data.get_data() or b""), url)
