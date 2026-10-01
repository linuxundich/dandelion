# SPDX-License-Identifier: GPL-3.0-or-later
"""KI in der Anwendung: Anbieter, Modell, API-Schlüssel, Datenschutzhinweis."""

from __future__ import annotations

from collections.abc import Callable
from gettext import gettext as _
from typing import TYPE_CHECKING

from gi.repository import Adw, Gtk

from .ai import PROVIDERS, AIError, AIProvider, create
from .ai.tasks import Context
from .core.models import Role

if TYPE_CHECKING:
    from .application import DandelionApplication

SECRET_OWNER = "ai"


class AIService:
    def __init__(self, app: DandelionApplication) -> None:
        self.app = app
        self.settings = app.settings

    @property
    def enabled(self) -> bool:
        return self.settings.get_boolean("ai-enabled")

    @property
    def provider_id(self) -> str:
        pid = self.settings.get_string("ai-provider")
        return pid if pid in PROVIDERS else "gemini"

    def provider(self, provider_id: str | None = None) -> AIProvider:
        return create(provider_id or self.provider_id, self.app.http)

    def model(self, provider_id: str | None = None) -> str:
        pid = provider_id or self.provider_id
        return self.settings.get_string(f"ai-model-{pid}") or self.provider(pid).default_model

    def set_model(self, provider_id: str, model: str) -> None:
        self.settings.set_string(f"ai-model-{provider_id}", model)

    async def api_key(self, provider_id: str | None = None) -> str | None:
        data = await self.app.secrets.get(SECRET_OWNER, provider_id or self.provider_id)
        return str(data["key"]) if data and data.get("key") else None

    async def set_api_key(self, provider_id: str, key: str) -> None:
        if key.strip():
            await self.app.secrets.set(SECRET_OWNER, provider_id,
                                       f"Dandelion: API-Schlüssel {self.provider(provider_id).name}",
                                       {"key": key.strip()})
        else:
            await self.app.secrets.delete(SECRET_OWNER, provider_id)

    async def context(self, role: Role | None) -> Context:
        key = await self.api_key()
        if not key:
            raise AIError(_("No API key for {provider} is stored. Add one in the preferences "
                            "under “AI”.").format(provider=self.provider().name))
        return Context(self.provider(), key, self.model(), role.ai_style if role else "")

    def confirm_privacy(self, parent: Gtk.Widget, images: bool,
                        then: Callable[[], None]) -> None:
        """Zeigt vor dem ersten Senden an einen Anbieter einen Datenschutzhinweis."""
        kind = "images" if images else "text"
        key = f"{self.provider_id}:{kind}"
        accepted = list(self.settings.get_strv("ai-privacy-accepted"))
        if key in accepted:
            then()
            return
        name = self.provider().name
        body = (_("Dandelion sends the selected image to {provider} to describe it.")
                if images else
                _("Dandelion sends the text of your post to {provider}.")).format(provider=name)
        body += "\n\n" + _("The provider processes the data under its own terms and may "
                           "store it. Do not send confidential content. Suggestions are never "
                           "applied without your confirmation.")
        dialog = Adw.AlertDialog(heading=_("Send to {provider}?").format(provider=name),
                                 body=body)
        dialog.add_response("cancel", _("_Cancel"))
        dialog.add_response("send", _("_Send"))
        dialog.set_response_appearance("send", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_close_response("cancel")

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            if response == "send":
                self.settings.set_strv("ai-privacy-accepted", [*accepted, key])
                then()

        dialog.connect("response", on_response)
        dialog.present(parent)
