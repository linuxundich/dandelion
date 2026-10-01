# SPDX-License-Identifier: GPL-3.0-or-later
"""xAI (Grok) über die OpenAI-kompatible Chat-Completions-Schnittstelle."""

from __future__ import annotations

from gettext import gettext as _
from typing import Any

from ..net.http import Request
from .base import AIError, AIProvider, ImageInput

API = "https://api.x.ai/v1"


class XAI(AIProvider):
    id = "xai"
    name = "xAI Grok"
    default_model = "grok-4.7"
    key_url = "https://console.x.ai/"
    preferred = ("grok-4.7", "grok-4.6", "grok-4.5")

    async def list_models(self, api_key: str) -> list[str]:
        resp = await self._send(Request("GET", f"{API}/models",
                                        headers={"Authorization": f"Bearer {api_key}"}))
        ids = [m["id"] for m in (resp.json() or {}).get("data", [])]
        return sorted((i for i in ids if i.startswith("grok") and "image" not in i
                       and "imagine" not in i), reverse=True)

    async def complete(self, api_key: str, model: str, system: str, text: str,
                       images: list[ImageInput] | None = None) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for img in images or []:
            content.append({"type": "image_url", "image_url": {"url": img.data_url()}})
        resp = await self._send(Request(
            "POST", f"{API}/chat/completions", headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content}]}, timeout=120))
        try:
            return str((resp.json() or {})["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise AIError(_("{provider} returned an empty answer.").format(provider=self.name),
                          resp.text()[:300]) from e
