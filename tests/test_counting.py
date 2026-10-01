# SPDX-License-Identifier: GPL-3.0-or-later
from dandelion.core.counting import (
    bluesky_count,
    bluesky_display_text,
    bluesky_shorten_url,
    find_hashtags,
    find_mentions,
    find_urls,
    mastodon_count,
)


def test_urls_trim_punctuation():
    urls = find_urls("Lies https://linuxundich.de/gnome-50. Und (https://example.org/a_(b)) !")
    assert [u.value for u in urls] == ["https://linuxundich.de/gnome-50", "https://example.org/a_(b)"]


def test_mastodon_url_counts_23():
    text = "Neu: https://linuxundich.de/2026/10/ein-sehr-langer-artikel-ueber-gnome-50"
    assert mastodon_count(text) == len("Neu: ") + 23


def test_mastodon_custom_url_length():
    assert mastodon_count("https://a.de/x", url_length=10) == 10


def test_mastodon_mention_without_domain():
    assert mastodon_count("Hallo @toff@social.tchncs.de!") == len("Hallo @toff!")


def test_mastodon_cw_counts():
    assert mastodon_count("abc", content_warning="Spoiler") == 10


def test_mastodon_emoji_graphemes():
    assert mastodon_count("👨‍👩‍👧 hi") == 4


def test_mentions_and_hashtags():
    text = "Danke @toff@social.tchncs.de und @lui #GNOME #50 https://x.de/#anker"
    assert [m.value for m in find_mentions(text)] == ["@toff@social.tchncs.de", "@lui"]
    assert [h.value for h in find_hashtags(text)] == ["#GNOME"]


def test_bluesky_shorten():
    assert bluesky_shorten_url("https://www.linuxundich.de/") == "linuxundich.de"
    assert bluesky_shorten_url("https://linuxundich.de/kurz") == "linuxundich.de/kurz"
    assert bluesky_shorten_url("https://linuxundich.de/2026/10/gnome-50-test") == \
        "linuxundich.de/2026/10/gnom..."


def test_bluesky_count_uses_short_url():
    text = "Test https://linuxundich.de/2026/10/gnome-50-test"
    assert bluesky_display_text(text) == "Test linuxundich.de/2026/10/gnom..."
    graphemes, nbytes = bluesky_count(text)
    assert graphemes == len("Test linuxundich.de/2026/10/gnom...")
    assert nbytes == graphemes


def test_bluesky_bytes():
    assert bluesky_count("ä👍🏽") == (2, 2 + 8)
