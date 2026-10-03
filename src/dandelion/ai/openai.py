# SPDX-License-Identifier: GPL-3.0-or-later
"""OpenAI über die Responses API."""

from __future__ import annotations

from gettext import gettext as _
from typing import Any

from ..net.http import Request
from .base import AIError, AIProvider, ImageInput

API = "https://api.openai.com/v1"


class OpenAI(AIProvider):
    id = "openai"
    name = "OpenAI"
    default_model = "gpt-6-luna"
    key_url = "https://platform.openai.com/api-keys"
    preferred = ("gpt-6-luna", "gpt-6.1-sol", "gpt-6-astra")

    async def list_models(self, api_key: str) -> list[str]:
        resp = await self._send(Request("GET", f"{API}/models",
                                        headers={"Authorization": f"Bearer {api_key}"}))
        ids = [m["id"] for m in (resp.json() or {}).get("data", [])]
        chat = [i for i in ids if i.startswith(("gpt-", "o")) and not any(
            x in i for x in ("audio", "realtime", "tts", "transcribe", "image", "embedding",
                             "search", "moderation"))]
        return sorted(chat, reverse=True)

    async def complete(self, api_key: str, model: str, system: str, text: str,
                       images: list[ImageInput] | None = None) -> str:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": text}]
        for img in images or []:
            content.append({"type": "input_image", "image_url": img.data_url()})

        def build(economical: bool) -> Request:
            body: dict[str, Any] = {"model": model, "instructions": system,
                                    "input": [{"role": "user", "content": content}]}
            if economical:
                body["reasoning"] = {"effort": "low"}
            return Request("POST", f"{API}/responses",
                           headers={"Authorization": f"Bearer {api_key}"}, json=body,
                           timeout=120)

        resp = await self._send_economical(model, build, "reasoning")
        data = resp.json() or {}
        if data.get("output_text"):
            return str(data["output_text"])
        parts = [c.get("text", "") for item in data.get("output", [])
                 if item.get("type") == "message"
                 for c in item.get("content", []) if c.get("type") == "output_text"]
        if not parts:
            raise AIError(_("{provider} returned an empty answer.").format(provider=self.name),
                          str(data)[:300])
        return "".join(parts)
