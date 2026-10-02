# SPDX-License-Identifier: GPL-3.0-or-later
from dandelion.core.counting import bluesky_count, mastodon_count, x_count
from dandelion.core.splitting import has_manual_breaks, split_thread


def masto(s):
    return mastodon_count(s)


def test_short_text_stays_one_part():
    assert split_thread("Kurz und gut.", masto, 500) == ["Kurz und gut."]


def test_paragraph_split_with_numbering():
    paras = ["Absatz eins " + "a" * 200, "Absatz zwei " + "b" * 200, "Absatz drei " + "c" * 200]
    parts = split_thread("\n\n".join(paras), masto, 300)
    assert len(parts) == 3
    assert parts[0].startswith("Absatz eins") and parts[0].endswith(" 1/3")
    assert parts[2].endswith(" 3/3")
    assert all(masto(p) <= 300 for p in parts)


def test_sentence_and_word_split():
    text = " ".join(f"Satz Nummer {i} mit etwas mehr Inhalt." for i in range(40))
    parts = split_thread(text, masto, 120, "plain")
    assert len(parts) > 3
    assert all(masto(p) <= 120 for p in parts)
    assert all(p.endswith(".") for p in parts)            # an Satzenden getrennt
    assert " ".join(parts) == text


def test_urls_are_never_cut_and_count_23():
    url = "https://linuxundich.de/" + "sehr-langer-pfad-" * 20
    text = "Lies das hier " + "x" * 260 + " " + url
    parts = split_thread(text, masto, 300)
    assert any(url in p for p in parts)
    assert all(masto(p) <= 300 for p in parts)


def test_manual_breaks():
    text = "Teil eins\n---\nTeil zwei\n  ---  \nTeil drei"
    assert has_manual_breaks(text)
    parts = split_thread(text, masto, 500, "thread-fraction")
    assert parts == ["Teil eins 🧵 1/3", "Teil zwei 🧵 2/3", "Teil drei 🧵 3/3"]


def test_bluesky_graphemes_and_x_weights():
    text = "👍 " * 400
    parts = split_thread(text, lambda s: bluesky_count(s)[0], 300)
    assert all(bluesky_count(p)[0] <= 300 for p in parts)
    cjk = "日本語のテキスト。" * 60
    parts = split_thread(cjk, x_count, 280)
    assert all(x_count(p) <= 280 for p in parts)


def test_numbering_reserve_with_many_parts():
    text = " ".join(["Wort"] * 2000)
    parts = split_thread(text, masto, 100)
    n = len(parts)
    assert n >= 10 and parts[-1].endswith(f" {n}/{n}")
    assert all(masto(p) <= 100 for p in parts)
