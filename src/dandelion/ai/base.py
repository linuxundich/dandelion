# SPDX-License-Identifier: GPL-3.0-or-later
"""Gemeinsame Schnittstelle der KI-Anbieter (Gemini, OpenAI, xAI, OpenRouter)."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from gettext import gettext as _

from ..net.http import HttpClient, NetworkError, Request, Response


class AIError(Exception):
    def __init__(self, message: str, detail: str = "", status: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.status = status


@dataclass
class ImageInput:
    mime: str
    data: bytes

    def data_url(self) -> str:
        return f"data:{self.mime};base64,{base64.b64encode(self.data).decode()}"

    def b64(self) -> str:
        return base64.b64encode(self.data).decode()


class AIProvider(ABC):
    id: str = ""
    name: str = ""
    #: Startwert, bis die Modellliste vom Anbieter geladen ist
    default_model: str = ""
    key_url: str = ""
    #: Bevorzugte Modelle in dieser Reihenfolge, falls vorhanden
    preferred: tuple[str, ...] = ()

    def __init__(self, http: HttpClient) -> None:
        self.http = http
        #: Modelle, die den Sparparameter (siehe _send_economical) abgelehnt haben
        self._no_effort: set[str] = set()

    @abstractmethod
    async def list_models(self, api_key: str) -> list[str]: ...

    @abstractmethod
    async def complete(self, api_key: str, model: str, system: str, text: str,
                       images: list[ImageInput] | None = None) -> str: ...

    def pick_default(self, models: list[str]) -> str:
        for want in self.preferred:
            if want in models:
                return want
        return models[0] if models else self.default_model

    async def _send_economical(self, model: str, build: Callable[[bool], Request],
                               hint: str) -> Response:
        """Schickt die Anfrage mit wenig Denkaufwand, falls das Modell das kann.

        Umformulieren, Hashtags und Alt-Text brauchen kein langes Nachdenken,
        und Denk-Tokens werden wie Ausgabe bezahlt. Nicht jedes Modell kennt
        den Parameter dafür: Lehnt es ihn ab (HTTP 400, die Meldung nennt
        `hint`), geht dieselbe Anfrage ohne ihn noch einmal raus, und das
        Modell bekommt ihn bis zum Neustart nicht mehr. Abgelehnte Anfragen
        kosten nichts.
        """
        if model not in self._no_effort:
            try:
                return await self._send(build(True))
            except AIError as e:
                if e.status != 400 or hint not in e.detail.lower():
                    raise
                self._no_effort.add(model)
        return await self._send(build(False))

    async def _send(self, req: Request) -> Response:
        try:
            resp = await self.http.send(req)
        except NetworkError as e:
            raise AIError(_("{provider} could not be reached. Check your internet "
                            "connection.").format(provider=self.name), str(e)) from e
        if resp.ok:
            return resp
        detail = resp.text()[:400]
        if resp.status in (401, 403):
            raise AIError(_("{provider} did not accept the API key.").format(
                provider=self.name), detail)
        if resp.status == 429:
            raise AIError(_("{provider}: limit reached or no credit left. Please try "
                            "again later.").format(provider=self.name), detail)
        if resp.status == 404:
            raise AIError(_("{provider} does not know this model. Choose another one in the "
                            "preferences.").format(provider=self.name), detail)
        raise AIError(_("{provider} reported an error (HTTP {status}).").format(
            provider=self.name, status=resp.status), detail, resp.status)
