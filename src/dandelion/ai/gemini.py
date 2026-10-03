# SPDX-License-Identifier: GPL-3.0-or-later
"""Google Gemini über die Gemini API (generateContent)."""

from __future__ import annotations

from gettext import gettext as _
from typing import Any

from ..net.http import Request
from .base import AIError, AIProvider, ImageInput

API = "https://generativelanguage.googleapis.com/v1beta"


class Gemini(AIProvider):
    id = "gemini"
    name = "Google Gemini"
    default_model = "gemini-3.6-flash"
    key_url = "https://aistudio.google.com/apikey"
    preferred = ("gemini-3.6-flash", "gemini-3.8-flash", "gemini-3.5-flash")

    async def list_models(self, api_key: str) -> list[str]:
        resp = await self._send(Request("GET", f"{API}/models", params={"pageSize": 200},
                                        headers={"x-goog-api-key": api_key}))
        out = []
        for m in (resp.json() or {}).get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            name = str(m.get("name", "")).removeprefix("models/")
            if name.startswith("gemini") and not any(
                    x in name for x in ("tts", "image", "live", "transcribe", "embedding")):
                out.append(name)
        return sorted(out, reverse=True)

    async def complete(self, api_key: str, model: str, system: str, text: str,
                       images: list[ImageInput] | None = None) -> str:
        parts: list[dict[str, Any]] = [{"text": text}]
        for img in images or []:
            parts.append({"inline_data": {"mime_type": img.mime, "data": img.b64()}})

        def build(economical: bool) -> Request:
            body: dict[str, Any] = {"systemInstruction": {"parts": [{"text": system}]},
                                    "contents": [{"role": "user", "parts": parts}]}
            if economical:
                body["generationConfig"] = {"thinkingConfig": {"thinkingLevel": "low"}}
            return Request("POST", f"{API}/models/{model}:generateContent",
                           headers={"x-goog-api-key": api_key}, json=body, timeout=120)

        resp = await self._send_economical(model, build, "thinking")
        data = resp.json() or {}
        try:
            cand = data["candidates"][0]
            # Gedanken-Zusammenfassungen (thought: true) gehören nicht in die Antwort
            return "".join(p.get("text", "") for p in cand["content"]["parts"]
                           if not p.get("thought"))
        except (KeyError, IndexError, TypeError) as e:
            reason = (data.get("promptFeedback") or {}).get("blockReason", "")
            raise AIError(_("{provider} returned no answer. {reason}").format(
                provider=self.name, reason=reason).strip(), str(data)[:300]) from e
