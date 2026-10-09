# SPDX-License-Identifier: GPL-3.0-or-later
"""KI-Anbieter. Neue Anbieter hier eintragen."""

from __future__ import annotations

from ..net.http import HttpClient
from .base import AIError, AIProvider, ImageInput
from .gemini import Gemini
from .openai import OpenAI
from .openrouter import OpenRouter
from .xai import XAI

PROVIDERS: dict[str, type[AIProvider]] = {
    Gemini.id: Gemini,
    OpenAI.id: OpenAI,
    XAI.id: XAI,
    OpenRouter.id: OpenRouter,
}


def create(provider_id: str, http: HttpClient) -> AIProvider:
    return PROVIDERS.get(provider_id, Gemini)(http)


__all__ = ["AIError", "AIProvider", "ImageInput", "PROVIDERS", "create"]
