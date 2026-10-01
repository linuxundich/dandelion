# SPDX-License-Identifier: GPL-3.0-or-later
"""Registry der Plattform-Backends. Neue Netzwerke hier eintragen."""

from __future__ import annotations

from ..core.secrets import SecretStore
from ..net.http import HttpClient
from .base import Platform
from .bluesky import Bluesky
from .mastodon import Mastodon

PLATFORM_CLASSES: dict[str, type[Platform]] = {
    Mastodon.id: Mastodon,
    Bluesky.id: Bluesky,
}


class Registry:
    def __init__(self, http: HttpClient, secrets: SecretStore) -> None:
        self.http = http
        self.secrets = secrets
        self._instances = {pid: cls(http, secrets) for pid, cls in PLATFORM_CLASSES.items()}

    def get(self, platform_id: str) -> Platform:
        return self._instances[platform_id]

    def all(self) -> list[Platform]:
        return list(self._instances.values())

    def __contains__(self, platform_id: str) -> bool:
        return platform_id in self._instances
