# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from dandelion.ai import AIError, ImageInput, create
from dandelion.ai import tasks
from dandelion.ai.tasks import Context, clean, parse_hashtags


def test_clean():
    assert clean('"Hallo Welt"') == "Hallo Welt"
    assert clean("„Hallo“") == "Hallo"
    assert clean("```\nText\n```") == "Text"
    assert clean('Er sagte "ja" und "nein"') == 'Er sagte "ja" und "nein"'


def test_parse_hashtags():
    assert parse_hashtags('["#Linux", "GNOME", "#linux", "Open Source"]') == \
        ["#Linux", "#GNOME", "#OpenSource"]
    assert parse_hashtags("#Wayland #GNOME50") == ["#Wayland", "#GNOME50"]


def test_openai_responses_api(http, run):
    http.add("POST", "https://api.openai.com/v1/responses", {"output": [
        {"type": "reasoning"},
        {"type": "message", "content": [{"type": "output_text", "text": "\"Kurz.\""}]}]})
    ctx = Context(create("openai", http), "sk-test", "gpt-6-luna", role_style="Locker, duzt")
    assert run(tasks.rephrase(ctx, "Lang und ausführlich.", "shorter")) == "Kurz."
    req = http.requests[-1]
    assert req.headers["Authorization"] == "Bearer sk-test"
    assert "Locker, duzt" in req.json["instructions"]
    assert req.json["input"][0]["content"][0] == {"type": "input_text",
                                                  "text": "Lang und ausführlich."}


def test_openai_image_and_models(http, run):
    http.add("GET", "https://api.openai.com/v1/models", {"data": [
        {"id": "gpt-6-luna"}, {"id": "gpt-6-astra"}, {"id": "gpt-realtime"},
        {"id": "text-embedding-3"}]})
    p = create("openai", http)
    models = run(p.list_models("k"))
    assert models == ["gpt-6-luna", "gpt-6-astra"]
    assert p.pick_default(models) == "gpt-6-luna"
    http.add("POST", "https://api.openai.com/v1/responses", {"output_text": "Eine Pusteblume."})
    ctx = Context(p, "k", "gpt-6-luna")
    text = run(tasks.alt_text(ctx, ImageInput("image/png", b"PNG"), 1500, "German"))
    assert text == "Eine Pusteblume."
    content = http.requests[-1].json["input"][0]["content"]
    assert content[1]["image_url"].startswith("data:image/png;base64,")


def test_gemini(http, run):
    http.add("POST", "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash"
             ":generateContent",
             {"candidates": [{"content": {"parts": [{"text": '["#Linux", "#GNOME"]'}]}}]})
    ctx = Context(create("gemini", http), "g-key", "gemini-3.6-flash")
    assert run(tasks.hashtags(ctx, "GNOME 50 ist da", "mastodon")) == ["#Linux", "#GNOME"]
    req = http.requests[-1]
    assert req.headers["x-goog-api-key"] == "g-key"
    assert "CamelCase" in req.json["systemInstruction"]["parts"][0]["text"]


def test_gemini_models_filter(http, run):
    http.add("GET", "https://generativelanguage.googleapis.com/v1beta/models", {"models": [
        {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/gemini-3.8-flash-tts", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/text-embedding", "supportedGenerationMethods": ["embedContent"]}]})
    assert run(create("gemini", http).list_models("k")) == ["gemini-3.6-flash"]


def test_xai_chat_completions(http, run):
    http.add("POST", "https://api.x.ai/v1/chat/completions",
             {"choices": [{"message": {"content": "Hello world"}}]})
    ctx = Context(create("xai", http), "x-key", "grok-4.7")
    assert run(tasks.translate(ctx, "Hallo Welt", "English")) == "Hello world"
    msgs = http.requests[-1].json["messages"]
    assert msgs[0]["role"] == "system" and "English" in msgs[0]["content"]


def test_adapt_mentions_limit(http, run):
    http.add("POST", "https://api.x.ai/v1/chat/completions",
             {"choices": [{"message": {"content": "kurz"}}]})
    ctx = Context(create("xai", http), "k", "grok-4.7")
    run(tasks.adapt(ctx, "lang", "bluesky", "Bluesky", 300))
    assert "300 characters" in http.requests[-1].json["messages"][0]["content"]


def test_errors(http, run):
    http.add("POST", "https://api.openai.com/v1/responses", {"error": "bad key"}, 401)
    ctx = Context(create("openai", http), "k", "m")
    with pytest.raises(AIError) as e:
        run(tasks.rephrase(ctx, "x", "correct"))
    assert "API key" in e.value.message


def test_alt_text_truncates(http, run):
    http.add("POST", "https://api.x.ai/v1/chat/completions",
             {"choices": [{"message": {"content": "Wort " * 100}}]})
    ctx = Context(create("xai", http), "k", "grok-4.7")
    text = run(tasks.alt_text(ctx, ImageInput("image/jpeg", b"J"), 50, "German"))
    assert len(text) <= 50 and text.endswith("…")


def test_low_effort_is_requested(http, run):
    http.add("POST", "https://api.openai.com/v1/responses", {"output_text": "Kurz."})
    ctx = Context(create("openai", http), "k", "gpt-6-luna")
    run(tasks.rephrase(ctx, "Lang.", "shorter"))
    assert http.requests[-1].json["reasoning"] == {"effort": "low"}

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash"
    http.add("POST", url, {"candidates": [{"content": {"parts": [
        {"text": "nachdenken", "thought": True}, {"text": "Kurz."}]}}]})
    ctx = Context(create("gemini", http), "g", "gemini-3.6-flash")
    assert run(tasks.rephrase(ctx, "Lang.", "shorter")) == "Kurz."
    assert http.requests[-1].json["generationConfig"] == {
        "thinkingConfig": {"thinkingLevel": "low"}}


def test_low_effort_falls_back_when_model_rejects_it(http, run):
    def handler(req):
        from dandelion.net.http import Response
        if "reasoning" in req.json:
            return Response(400, {"content-type": "application/json"},
                            b'{"error":{"message":"Unsupported parameter: reasoning.effort"}}',
                            req.full_url())
        return Response(200, {"content-type": "application/json"},
                        b'{"output_text":"Kurz."}', req.full_url())

    http.add("POST", "https://api.openai.com/v1/responses", handler)
    p = create("openai", http)
    ctx = Context(p, "k", "gpt-old")
    assert run(tasks.rephrase(ctx, "Lang.", "shorter")) == "Kurz."
    assert len(http.requests) == 2
    # Beim nächsten Mal gleich ohne
    assert run(tasks.rephrase(ctx, "Lang.", "shorter")) == "Kurz."
    assert len(http.requests) == 3 and "reasoning" not in http.requests[-1].json


def test_other_bad_requests_are_not_retried(http, run):
    http.add("POST", "https://api.openai.com/v1/responses",
             {"error": {"message": "Invalid input"}}, status=400)
    ctx = Context(create("openai", http), "k", "gpt-6-luna")
    with pytest.raises(AIError) as e:
        run(tasks.rephrase(ctx, "Lang.", "shorter"))
    assert e.value.status == 400 and len(http.requests) == 1


def test_alt_text_revision_includes_previous_and_request(http, run):
    http.add("POST", "https://api.openai.com/v1/responses", {"output_text": "Kürzer."})
    ctx = Context(create("openai", http), "k", "gpt-6-luna")
    run(tasks.alt_text(ctx, ImageInput("image/png", b"PNG"), None, "German", "",
                       "Ein langer Text.", "kürzer"))
    prompt = http.requests[-1].json["input"][0]["content"][0]["text"]
    assert "Ein langer Text." in prompt and "kürzer" in prompt
