# SPDX-License-Identifier: GPL-3.0-or-later
"""Gemeinsame Schnittstelle aller Plattform-Backends.

Ein Backend kennt Limits und Zählweise seiner Plattform, prüft einen
Beitrag, lädt Medien hoch, veröffentlicht und löscht. Login-Abläufe
unterscheiden sich stark und liegen deshalb als eigene Funktionen im
jeweiligen Modul (siehe mastodon.py, bluesky.py).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from gettext import gettext as _
from typing import Any

from ..core.models import Media, Profile, TargetPart
from ..core.secrets import SecretStore
from ..net.http import HttpClient, NetworkError, Request, Response


@dataclass
class PlatformLimits:
    max_chars: int
    max_bytes: int | None = None
    url_weight: int | None = None
    max_images: int = 4
    max_videos: int = 1
    allow_mixed_media: bool = False
    image_mime_types: tuple[str, ...] = ("image/jpeg", "image/png", "image/gif", "image/webp")
    video_mime_types: tuple[str, ...] = ("video/mp4",)
    max_image_bytes: int | None = None
    max_video_bytes: int | None = None
    alt_text_max: int | None = None
    alt_text_required: bool = False
    supports_content_warning: bool = False
    content_labels: tuple[str, ...] = ()
    visibility_options: tuple[str, ...] = ()
    max_languages: int = 0
    supports_threads: bool = True
    client_link_card: bool = False
    preview_truncate: int | None = None   # ab hier „mehr anzeigen“ in der Vorschau

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> PlatformLimits:
        raw = json.loads(data)
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        for k, v in known.items():
            if isinstance(v, list):
                known[k] = tuple(v)
        return cls(**known)


@dataclass
class Count:
    used: int
    limit: int
    bytes_used: int | None = None
    bytes_limit: int | None = None

    @property
    def over(self) -> bool:
        if self.used > self.limit:
            return True
        return self.bytes_limit is not None and (self.bytes_used or 0) > self.bytes_limit

    @property
    def ratio(self) -> float:
        return self.used / self.limit if self.limit else 0.0


@dataclass
class Issue:
    severity: str          # "error" | "warning"
    code: str
    message: str
    media_index: int | None = None


@dataclass
class Composition:
    """Der fertige Inhalt für genau ein Profil."""

    text: str
    content_warning: str = ""
    language: str | None = None
    visibility: str | None = None
    content_label: str | None = None
    media: list[Media] = field(default_factory=list)


class PlatformError(Exception):
    """Fehler mit verständlicher Meldung für die UI.

    `detail` enthält technische Informationen ohne Secrets.
    """

    def __init__(self, message: str, detail: str = "", *, retryable: bool = False,
                 auth: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.retryable = retryable
        self.auth = auth


def error_from_status(status: int, detail: str = "") -> PlatformError:
    if status in (401, 403):
        return PlatformError(_("The login has expired. Please sign in again."), detail, auth=True)
    if status == 404:
        return PlatformError(_("The server could not find the requested resource."), detail)
    if status == 413:
        return PlatformError(_("The file is too large for this server."), detail)
    if status == 422:
        return PlatformError(_("The server rejected the post."), detail)
    if status == 429:
        return PlatformError(_("Too many requests. Please try again later."), detail,
                             retryable=True)
    if status >= 500:
        return PlatformError(_("The server is currently unavailable."), detail, retryable=True)
    return PlatformError(_("Unexpected answer from the server (HTTP {status}).").format(
        status=status), detail)


class Platform(ABC):
    id: str = ""
    name: str = ""
    #: CSS-Klasse und Farbe der stilisierten Darstellung (keine Markenlogos)
    style_class: str = ""

    def __init__(self, http: HttpClient, secrets: SecretStore) -> None:
        self.http = http
        self.secrets = secrets

    # -- Limits und Prüfung (synchron, schnell) --------------------------
    @abstractmethod
    def default_limits(self) -> PlatformLimits: ...

    def limits_for(self, profile: Profile) -> PlatformLimits:
        if profile.limits_json:
            try:
                return PlatformLimits.from_json(profile.limits_json)
            except (ValueError, TypeError):
                pass
        return self.default_limits()

    @abstractmethod
    def count(self, comp: Composition, limits: PlatformLimits) -> Count: ...

    def cost_notice(self, comp: Composition) -> str | None:
        """Hinweis auf Kosten pro Beitrag (nur X), sonst None."""
        return None

    def display_text(self, text: str) -> str:
        """Text so, wie er auf der Plattform erscheint (für die Vorschau)."""
        return text

    # -- Netzwerk ----------------------------------------------------------
    async def fetch_limits(self, profile: Profile) -> PlatformLimits:
        return self.default_limits()

    @abstractmethod
    async def refresh_profile(self, profile: Profile) -> Profile:
        """Prüft die Anmeldung, aktualisiert Name, Avatar und Status."""

    @abstractmethod
    async def upload_media(self, profile: Profile, media: Media) -> str:
        """Lädt ein Medium hoch und liefert eine serialisierte Referenz."""

    @abstractmethod
    async def post(self, profile: Profile, comp: Composition, media_refs: list[str], *,
                   reply_to: TargetPart | None, root: TargetPart | None,
                   idempotency_key: str) -> TargetPart: ...

    @abstractmethod
    async def delete(self, profile: Profile, part: TargetPart) -> None: ...

    async def logout(self, profile: Profile) -> None:
        await self.secrets.delete(profile.uuid)


@dataclass
class AppLogin:
    """Laufender Login über eine eigene Entwickler-App (X, LinkedIn, Facebook)."""

    platform_id: str
    url: str
    redirect_uri: str
    state: str
    client_id: str
    client_secret: str = ""
    verifier: str = ""


class AppPlatform(Platform):
    """Plattform, für die Nutzer eine eigene Entwickler-App anlegen.

    Ein Client-Secret ist in einer Desktop-App nicht geheim; deshalb trägt
    jeder Nutzer die Zugangsdaten seiner eigenen App ein (libsecret).
    """

    #: "none", "optional" oder "required"
    client_secret_mode: str = "required"
    redirect_port: int = 8742
    redirect_host: str = "127.0.0.1"
    portal_url: str = ""
    scopes: str = ""

    @property
    def redirect_uri(self) -> str:
        return f"http://{self.redirect_host}:{self.redirect_port}/callback"

    def _app_owner(self) -> str:
        return f"app:{self.id}"

    async def client_credentials(self) -> dict[str, str] | None:
        data = await self.secrets.get(self._app_owner(), "client-credentials")
        return {k: str(v) for k, v in data.items()} if data else None

    async def set_client_credentials(self, client_id: str, client_secret: str) -> None:
        await self.secrets.set(self._app_owner(), "client-credentials",
                               f"Dandelion: {self.name} App", {
                                   "client_id": client_id.strip(),
                                   "client_secret": client_secret.strip()})

    @abstractmethod
    def begin_app_login(self, client_id: str, client_secret: str) -> AppLogin: ...

    @abstractmethod
    async def complete_app_login(self, login: AppLogin,
                                 code: str) -> list[tuple[Profile, dict[str, Any]]]:
        """Tauscht den Code und liefert ein oder mehrere Profile (Facebook: Seiten)."""

    async def store_credentials(self, profile: Profile, secret: dict[str, Any]) -> None:
        await self.secrets.set(profile.uuid, "oauth", secret_label(self, profile), secret)

    async def _token_data(self, profile: Profile) -> dict[str, Any]:
        data = await self.secrets.get(profile.uuid, "oauth")
        if not data or not data.get("access_token"):
            raise PlatformError(_("No login data found. Please sign in again."), auth=True)
        return data

    async def _send(self, req: Request) -> Response:
        try:
            resp = await self.http.send(req)
        except NetworkError as e:
            raise PlatformError(_("{platform} could not be reached. Check your internet "
                                  "connection.").format(platform=self.name), str(e),
                                retryable=True) from e
        if resp.ok:
            return resp
        raise self._error(resp)

    def _error(self, resp: Response) -> PlatformError:
        detail = resp.text()[:400]
        return error_from_status(resp.status, detail)


def secret_label(platform: Platform, profile: Profile) -> str:
    return f"Dandelion: {platform.name} {profile.full_handle}"


def json_or_text(body: Any) -> str:
    try:
        return json.dumps(body)[:500]
    except (TypeError, ValueError):
        return str(body)[:500]
