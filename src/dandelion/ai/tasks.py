# SPDX-License-Identifier: GPL-3.0-or-later
"""Aufgaben des KI-Assistenten: Prompts bauen und Antworten bereinigen.

Der Assistent schlägt nur vor. Was er liefert, landet in einem Vorschlag,
den die Nutzerin oder der Nutzer übernimmt oder verwirft.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .base import AIProvider, ImageInput

BASE_RULES = (
    "You help to write posts for social networks. "
    "Return only the resulting post text: no quotes around it, no explanations, no "
    "markdown, no headings. Keep URLs, @mentions and existing hashtags exactly as they "
    "are unless you are asked to change them. Do not invent facts. "
    "Answer in the language of the post unless a different language is requested."
)

REPHRASE = {
    "shorter": "Make the post noticeably shorter while keeping the key message.",
    "longer": "Make the post a bit longer and more detailed without inventing facts.",
    "casual": "Rewrite the post in a more casual, friendly tone.",
    "factual": "Rewrite the post in a more factual, neutral tone.",
    "correct": "Only fix spelling, grammar and punctuation. Change nothing else.",
}

#: Hashtag-Gepflogenheiten je Plattform
HASHTAG_STYLE = {
    "mastodon": "Mastodon: hashtags matter for discovery, use 2 to 4 CamelCase hashtags "
                "at the end.",
    "bluesky": "Bluesky: use at most 1 or 2 hashtags, or none.",
    "x": "X: use at most 1 or 2 hashtags inside or after the text.",
    "linkedin": "LinkedIn: a professional tone and 3 to 5 hashtags at the end are common.",
    "facebook": "Facebook: hashtags are rarely used, use none or one.",
}


@dataclass
class Context:
    provider: AIProvider
    api_key: str
    model: str
    role_style: str = ""

    def system(self, extra: str = "") -> str:
        parts = [BASE_RULES]
        if self.role_style.strip():
            parts.append(f"Style and tone of this account: {self.role_style.strip()}")
        if extra:
            parts.append(extra)
        return "\n\n".join(parts)


def clean(text: str) -> str:
    """Entfernt Code-Zäune, umschließende Anführungszeichen und Leerraum."""
    text = text.strip()
    fence = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    pairs = (('"', '"'), ("„", "“"), ("“", "”"), ("«", "»"), ("'", "'"))
    for left, right in pairs:
        if len(text) > 1 and text.startswith(left) and text.endswith(right) \
                and text.count(left) == 1 + (left == right):
            text = text[1:-1].strip()
    return text


def parse_hashtags(answer: str, limit: int = 10) -> list[str]:
    answer = clean(answer)
    tags: list[str] = []
    try:
        data = json.loads(answer)
        if isinstance(data, list):
            tags = [str(x) for x in data]
    except ValueError:
        tags = re.findall(r"#?([\w\-]+)", answer)
    out: list[str] = []
    for tag in tags:
        tag = "#" + tag.strip().lstrip("#").replace(" ", "")
        if len(tag) > 1 and tag.lower() not in (t.lower() for t in out):
            out.append(tag)
    return out[:limit]


async def rephrase(ctx: Context, text: str, mode: str) -> str:
    answer = await ctx.provider.complete(ctx.api_key, ctx.model, ctx.system(REPHRASE[mode]),
                                         text)
    return clean(answer)


async def translate(ctx: Context, text: str, language: str) -> str:
    answer = await ctx.provider.complete(
        ctx.api_key, ctx.model,
        ctx.system(f"Translate the post into {language}. Keep the meaning and tone."), text)
    return clean(answer)


async def adapt(ctx: Context, text: str, platform_id: str, platform_name: str,
                max_chars: int) -> str:
    extra = (f"Adapt the post for {platform_name}. It must not be longer than "
             f"{max_chars} characters; URLs count as 23 characters. "
             f"{HASHTAG_STYLE.get(platform_id, '')}")
    answer = await ctx.provider.complete(ctx.api_key, ctx.model, ctx.system(extra), text)
    return clean(answer)


async def hashtags(ctx: Context, text: str, platform_id: str | None = None,
                   count: int = 8) -> list[str]:
    extra = (f"Suggest up to {count} fitting hashtags for the post. Return only a JSON "
             f"array of strings, for example [\"#Linux\", \"#GNOME\"]. Prefer established "
             f"hashtags. {HASHTAG_STYLE.get(platform_id or '', '')}")
    answer = await ctx.provider.complete(ctx.api_key, ctx.model, ctx.system(extra), text)
    return parse_hashtags(answer, count)


async def alt_text(ctx: Context, image: ImageInput, max_chars: int | None,
                   language: str, context_text: str = "", previous: str = "",
                   instruction: str = "") -> str:
    limit = f" Use at most {max_chars} characters." if max_chars else ""
    system = (
        "You write alt text for images in social media posts, for people who cannot see "
        f"the image. Describe what is important, concise and objective, in {language}. "
        "Transcribe important text that is visible in the image. Do not start with "
        f"\"Image of\" or \"Picture of\". Return only the alt text.{limit}")
    prompt = "Write the alt text for this image."
    if context_text.strip():
        prompt += f"\n\nThe post it belongs to:\n{context_text.strip()[:1500]}"
    if previous.strip() and instruction.strip():
        # Rückfrage im Chat: Der Dienst ist zustandslos, also stehen der letzte
        # Vorschlag und die Bitte im selben Auftrag.
        prompt += (f"\n\nYour previous suggestion:\n{previous.strip()}\n\n"
                   f"Revise it according to this request: {instruction.strip()[:500]}")
    answer = await ctx.provider.complete(ctx.api_key, ctx.model, system, prompt, [image])
    result = clean(answer)
    if max_chars and len(result) > max_chars:
        result = result[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return result
