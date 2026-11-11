# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, datetime, timedelta

import pytest
from helpers import setup_world

from dandelion.reader.base import ReadScopeMissing
from dandelion.reader.content import relative_time, to_markup, to_text
from dandelion.reader.mastodon import parse_status
from dandelion.reader.service import ReaderService

ACCOUNT = {"id": "7", "username": "mara", "acct": "mara@fosstodon.org",
           "display_name": "Mara Vogel", "avatar_static": "https://x/a.png", "url": "https://x/@mara"}


def status(sid="100", **kw):
    base = {"id": sid, "created_at": "2026-11-11T10:00:00.000Z", "account": ACCOUNT,
            "content": "<p>Hallo <a href=\"https://x/tags/gnome\" class=\"mention hashtag\">"
                       "#<span>gnome</span></a></p>",
            "spoiler_text": "", "sensitive": False, "media_attachments": [],
            "replies_count": 1, "reblogs_count": 2, "favourites_count": 3,
            "url": "https://x/@mara/100"}
    base.update(kw)
    return base


# -- Inhalt ------------------------------------------------------------------
def test_markup_basic():
    out = to_markup('<p>Hallo <strong>Welt</strong> &amp; <a href="https://a.b/?x=1&amp;y=2">Link</a></p>'
                    "<p>Zweiter Absatz<br>mit Umbruch</p>")
    assert out == ('Hallo <b>Welt</b> &amp; <a href="https://a.b/?x=1&amp;y=2">Link</a>'
                   "\n\nZweiter Absatz\nmit Umbruch")


def test_markup_hides_invisible_and_ellipsis():
    out = to_markup('<a href="https://example.org/a/b"><span class="invisible">https://</span>'
                    '<span class="ellipsis">example.org/a</span>'
                    '<span class="invisible">/b</span></a>')
    assert out == '<a href="https://example.org/a/b">example.org/a…</a>'


def test_markup_drops_unsafe_links_and_tags():
    out = to_markup('<p><script>alert(1)</script><a href="javascript:x">Klick</a> <img src="x"></p>')
    assert "javascript" not in out and "<img" not in out and "<a" not in out
    assert "Klick" in out


def test_markup_is_well_formed_for_broken_html():
    out = to_markup("<p>offen <b>fett <i>kursiv")
    assert out.count("<b>") == out.count("</b>") and out.count("<i>") == out.count("</i>")


def test_markup_lists_and_text():
    assert to_markup("<ul><li>eins</li><li>zwei</li></ul>") == "• eins\n• zwei"
    assert to_text("<p>a &lt; b</p>") == "a < b"


def test_relative_time():
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    def ago(**kw):
        return relative_time((now - timedelta(**kw)).isoformat(), now)
    assert ago(seconds=5) == "now"
    assert ago(minutes=9) == "9 min"
    assert ago(hours=3) == "3 h"
    assert ago(days=2) == "2 d"
    assert relative_time("2026-11-11T11:59:00.000Z", now) == "1 min"


# -- Beiträge ----------------------------------------------------------------
def test_parse_status_plain():
    post = parse_status(status(media_attachments=[
        {"type": "image", "url": "https://x/i.png", "preview_url": "https://x/p.png",
         "description": "Ein Bild"}], spoiler_text="CW", sensitive=True,
        card={"url": "https://l/", "title": "Titel", "description": "", "image": None}, poll={"id": "1"}))
    assert post.id == "100" and post.account.name == "Mara Vogel" and post.boosted_by is None
    assert (post.replies, post.boosts, post.likes) == (1, 2, 3)
    assert post.media[0].alt == "Ein Bild" and post.spoiler == "CW" and post.sensitive
    assert post.card.title == "Titel" and post.has_poll


def test_parse_status_boost_uses_original():
    booster = dict(ACCOUNT, id="9", acct="ben", display_name="Ben")
    original = status("55", content="<p>Original</p>")
    post = parse_status({"id": "200", "created_at": "2026-11-11T11:00:00.000Z",
                         "account": booster, "reblog": original, "content": ""})
    assert post.id == "200" and post.boosted_by.name == "Ben"
    assert post.account.name == "Mara Vogel" and "Original" in post.html


# -- Dienst, Cache -----------------------------------------------------------
def test_home_fetch_caches_and_pages(http, run):
    store, secrets, reg, role, masto, bsky = setup_world(http)
    run(secrets.set(masto.uuid, "oauth", "x", {"access_token": "tok"}))
    first = [status("30", created_at="2026-11-11T10:03:00.000Z"),
             status("20", created_at="2026-11-11T10:02:00.000Z")]
    older = [status("10", created_at="2026-11-11T10:01:00.000Z")]

    def handler(req):
        from dandelion.net.http import Response
        import json
        data = older if "max_id=20" in req.full_url() else first
        return Response(200, {"content-type": "application/json"}, json.dumps(data).encode(),
                        req.full_url())
    http.add("GET", "https://social.example/api/v1/timelines/home", handler)

    service = ReaderService(store, reg)
    assert service.cached_home(masto) == []
    posts = run(service.refresh_home(masto))
    assert [p.id for p in posts] == ["30", "20"]
    req = http.find("GET", "https://social.example/api/v1/timelines/home")[0]
    assert req.headers["Authorization"] == "Bearer tok"
    # zweites Fenster liest nur noch aus dem Cache
    assert [p.id for p in service.cached_home(masto)] == ["30", "20"]
    posts = run(service.load_older(masto))
    assert [p.id for p in posts] == ["30", "20", "10"]


def test_cache_keeps_limit_and_updates_counts(http, run):
    from dandelion.reader import cache as cache_mod
    store, *_ , masto, _b = setup_world(http)
    c = cache_mod.FeedCache(store)
    items = [status(str(i), created_at=f"2026-11-11T10:{i // 60:02d}:{i % 60:02d}.000Z")
             for i in range(cache_mod.KEEP_PER_FEED + 20)]
    c.save(masto.id, "home", items)
    assert len(c.load(masto.id, "home", 10_000)) == cache_mod.KEEP_PER_FEED
    c.save(masto.id, "home", [status("419", created_at="2026-11-11T10:06:59.000Z",
                                     favourites_count=99)])
    assert c.load(masto.id, "home", 1)[0]["favourites_count"] == 99


def test_other_networks_have_no_reader(http):
    store, secrets, reg, role, masto, bsky = setup_world(http)
    service = ReaderService(store, reg)
    assert service.can_read(masto) and not service.can_read(bsky)
    assert service.reader_for(bsky) is None and service.cached_home(bsky) == []


def test_missing_read_scope(http, run):
    store, secrets, reg, role, masto, bsky = setup_world(http)
    run(secrets.set(masto.uuid, "oauth", "x", {"access_token": "old"}))
    http.add("GET", "https://social.example/api/v1/timelines/home",
             {"error": "This action is outside the authorized scopes"}, status=403)
    with pytest.raises(ReadScopeMissing):
        run(ReaderService(store, reg).refresh_home(masto))
    http.add("GET", "https://social.example/api/v1/timelines/home", {"error": "nope"}, status=401)
    from dandelion.platforms.base import PlatformError
    with pytest.raises(PlatformError) as e:
        run(ReaderService(store, reg).refresh_home(masto))
    assert not isinstance(e.value, ReadScopeMissing) and e.value.auth
