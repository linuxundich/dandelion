# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenRouter: ein Schlüssel für viele Modelle, OpenAI-kompatible Chat-Completions."""

from __future__ import annotations

from gettext import gettext as _
from typing import Any

from ..net.http import Request
from .base import AIError, AIProvider, ImageInput

API = "https://openrouter.ai/api/v1"


class OpenRouter(AIProvider):
    id = "openrouter"
    name = "OpenRouter"
    default_model = "google/gemini-3.6-flash"
    key_url = "https://openrouter.ai/keys"
    preferred = ("google/gemini-3.6-flash", "openai/gpt-6-luna", "x-ai/grok-4.7")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}", "X-Title": "Dandelion",
                "HTTP-Referer": "https://github.com/linuxundich/dandelion"}

    async def list_models(self, api_key: str) -> list[str]:
        resp = await self._send(Request("GET", f"{API}/models",
                                        headers=self._headers(api_key)))
        ids = []
        for m in (resp.json() or {}).get("data", []):
            arch = m.get("architecture") or {}
            # Bilder müssen rein können (Alt-Text), Text muss herauskommen.
            if "image" in (arch.get("input_modalities") or []) \
                    and "text" in (arch.get("output_modalities") or ["text"]):
                ids.append(m["id"])
        return sorted(ids)

    async def complete(self, api_key: str, model: str, system: str, text: str,
                       images: list[ImageInput] | None = None) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for img in images or []:
            content.append({"type": "image_url", "image_url": {"url": img.data_url()}})

        def build(economical: bool) -> Request:
            body: dict[str, Any] = {"model": model, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content}]}
            if economical:
                body["reasoning"] = {"effort": "low"}
            return Request("POST", f"{API}/chat/completions",
                           headers=self._headers(api_key), json=body, timeout=120)

        resp = await self._send_economical(model, build, "reasoning")
        try:
            return str((resp.json() or {})["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as e:
            raise AIError(_("{provider} returned an empty answer.").format(provider=self.name),
                          resp.text()[:300]) from e
