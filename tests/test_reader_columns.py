# SPDX-License-Identifier: GPL-3.0-or-later
import json

from helpers import setup_world
from test_reader import status
from test_reader_bluesky import post_view, session

from dandelion.core.models import DeckColumnSpec
from dandelion.net.http import Response
from dandelion.reader.base import HOME, NOTIFICATIONS
from dandelion.reader.mastodon import path_for
from dandelion.reader.service import ReaderService

M = "https://social.example"
P = "https://pds.example/xrpc/"


def world(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "x", {"access_token": "tok"}))
    session(secrets, b)
    http.add("GET", f"{M}/api/v1/markers", {})
    return store, ReaderService(store, reg), role, m, b


# -- Spalten speichern ---------------------------------------------------------
def test_columns_default_saved_and_reset(http, run):
    store, service, role, m, b = world(http, run)
    default = service.columns(role)
    assert [(c.profile_id, c.kind) for c in default] == [(m.id, "profile"), (b.id, "profile")]
    service.save_columns(role, [
        DeckColumnSpec(role.id, b.id, "profile"),
        DeckColumnSpec(role.id, m.id, "feed", "list:12", "Linux news"),
        DeckColumnSpec(role.id, m.id, "feed", "tag:gnome", "#gnome")])
    saved = service.columns(role)
    assert [(c.kind, c.feed, c.title) for c in saved] == [
        ("profile", "", ""), ("feed", "list:12", "Linux news"), ("feed", "tag:gnome", "#gnome")]
    assert [c.position for c in saved] == [0, 1, 2]
    service.save_columns(role, [])                       # leer = Standard
    assert len(service.columns(role)) == 2


def test_removing_a_profile_removes_its_columns(http, run):
    store, service, role, m, b = world(http, run)
    service.save_columns(role, [DeckColumnSpec(role.id, m.id, "feed", "bookmarks", "Bookmarks"),
                                DeckColumnSpec(role.id, b.id, "profile")])
    store.delete_profile(m.id)
    assert [c.profile_id for c in service.columns(role)] == [b.id]


# -- Mastodon ------------------------------------------------------------------
def test_mastodon_feed_paths():
    assert path_for("list:12") == "/api/v1/timelines/list/12"
    assert path_for("tag:gnome") == "/api/v1/timelines/tag/gnome"
    assert path_for("tag:übung") == "/api/v1/timelines/tag/%C3%BCbung"
    assert path_for("bookmarks") == "/api/v1/bookmarks"


def test_mastodon_list_and_tag_columns(http, run):
    store, service, role, m, b = world(http, run)
    http.add("GET", f"{M}/api/v1/timelines/list/12", [status("30", created_at="2026-11-11T10:03:00Z")])
    http.add("GET", f"{M}/api/v1/timelines/tag/gnome", [status("40", created_at="2026-11-11T10:04:00Z")])
    assert [p.id for p in run(service.refresh(m, "list:12"))] == ["30"]
    assert [p.id for p in run(service.refresh(m, "tag:gnome"))] == ["40"]
    assert service.cached(m, HOME) == []                 # getrennte Listen im Cache


def test_bookmarks_page_with_link_header(http, run):
    store, service, role, m, b = world(http, run)

    def bookmarks(req):
        if "max_id=777" in req.full_url():
            data, headers = [status("5", created_at="2026-11-11T09:00:00Z")], {}
        else:
            data = [status("9", created_at="2026-11-11T10:00:00Z")]
            headers = {"link": f'<{M}/api/v1/bookmarks?max_id=777>; rel="next", '
                               f'<{M}/api/v1/bookmarks?min_id=900>; rel="prev"'}
        return Response(200, {"content-type": "application/json", **headers},
                        json.dumps(data).encode(), req.full_url())
    http.add("GET", f"{M}/api/v1/bookmarks", bookmarks)
    assert [p.id for p in run(service.refresh(m, "bookmarks"))] == ["9"]
    # nicht die ID des ältesten Beitrags, sondern der Cursor aus dem Link-Header
    assert [p.id for p in run(service.load_older(m, "bookmarks"))] == ["9", "5"]


def test_mastodon_sources(http, run):
    store, service, role, m, b = world(http, run)
    http.add("GET", f"{M}/api/v1/lists", [{"id": "12", "title": "Linux news"}])
    http.add("GET", f"{M}/api/v1/followed_tags", [{"name": "gnome"}, {"name": "flatpak"}])
    sources = run(service.sources(m))
    assert [(s.kind, s.feed, s.title) for s in sources] == [
        ("list", "list:12", "Linux news"), ("tag", "tag:gnome", "#gnome"),
        ("tag", "tag:flatpak", "#flatpak"), ("bookmarks", "bookmarks", "Bookmarks"),
        ("favourites", "favourites", "Favourites")]


# -- Bluesky -------------------------------------------------------------------
def test_bluesky_feed_list_tag_bookmarks_likes(http, run):
    store, service, role, m, b = world(http, run)
    view = lambda n: post_view(f"at://x/app.bsky.feed.post/{n}")  # noqa: E731
    http.add("GET", P + "app.bsky.feed.getFeed", {"feed": [{"post": view(1)}], "cursor": "c"})
    http.add("GET", P + "app.bsky.feed.getListFeed", {"feed": [{"post": view(2)}]})
    http.add("GET", P + "app.bsky.feed.searchPosts", {"posts": [view(3)]})
    http.add("GET", P + "app.bsky.bookmark.getBookmarks",
             {"bookmarks": [{"item": view(4)}, {"item": {"$type": "app.bsky.feed.defs#notFoundPost"}}]})
    http.add("GET", P + "app.bsky.feed.getActorLikes", {"feed": [{"post": view(5)}]})
    for feed, n in (("feed:at://g/app.bsky.feed.generator/f", 1), ("list:at://l/app.bsky.graph.list/x", 2),
                    ("tag:gnome", 3), ("bookmarks", 4), ("favourites", 5)):
        posts = run(service.refresh(b, feed))
        assert [p.id for p in posts] == [f"at://x/app.bsky.feed.post/{n}"], feed
    assert "feed=at%3A%2F%2Fg%2Fapp.bsky.feed.generator%2Ff" in \
        http.find("GET", P + "app.bsky.feed.getFeed")[0].full_url()
    assert "q=%23gnome" in http.find("GET", P + "app.bsky.feed.searchPosts")[0].full_url()
    assert "actor=did%3Aplc%3Aabc" in http.find("GET", P + "app.bsky.feed.getActorLikes")[0].full_url()


def test_bluesky_sources(http, run):
    store, service, role, m, b = world(http, run)
    http.add("GET", P + "app.bsky.actor.getPreferences", {"preferences": [
        {"$type": "app.bsky.actor.defs#savedFeedsPrefV2", "items": [
            {"type": "timeline", "value": "following", "pinned": True},
            {"type": "feed", "value": "at://g/app.bsky.feed.generator/f", "pinned": True},
            {"type": "list", "value": "at://l/app.bsky.graph.list/x", "pinned": False}]}]})
    http.add("GET", P + "app.bsky.feed.getFeedGenerators",
             {"feeds": [{"uri": "at://g/app.bsky.feed.generator/f", "displayName": "Linux Devs"}]})
    http.add("GET", P + "app.bsky.graph.getList", {"list": {"name": "Rust"}})
    sources = run(service.sources(b))
    assert [(s.kind, s.title) for s in sources] == [
        ("feed", "Linux Devs"), ("list", "Rust"), ("bookmarks", "Bookmarks"), ("favourites", "Likes")]
    assert sources[0].feed == "feed:at://g/app.bsky.feed.generator/f"


# -- Stream-Ereignisse -----------------------------------------------------------
def event(kind, payload):
    return {"stream": ["user"], "event": kind,
            "payload": payload if isinstance(payload, str) else json.dumps(payload)}


def test_stream_events_update_cache(http, run):
    store, service, role, m, b = world(http, run)
    st = status("70", created_at="2026-11-11T10:05:00Z")
    assert service.handle_stream_event(m, event("update", st)) == HOME
    assert [p.id for p in service.cached(m, HOME)] == ["70"]
    edited = dict(st, content="<p>bearbeitet</p>")
    assert service.handle_stream_event(m, event("status.update", edited)) == HOME
    assert "bearbeitet" in service.cached(m, HOME)[0].html and len(service.cached(m, HOME)) == 1
    assert service.handle_stream_event(m, event("delete", "70")) == HOME
    assert service.cached(m, HOME) == []


def test_stream_notifications_and_noise(http, run):
    store, service, role, m, b = world(http, run)
    note = {"id": "5", "type": "favourite", "created_at": "2026-11-11T10:00:00Z",
            "account": status("1")["account"], "status": status("55")}
    assert service.handle_stream_event(m, event("notification", note)) == NOTIFICATIONS
    assert service.cached(m, NOTIFICATIONS)[0].reason == "favourite"
    admin = dict(note, id="6", type="admin.sign_up")
    assert service.handle_stream_event(m, event("notification", admin)) is None
    assert service.handle_stream_event(m, event("filters_changed", "")) is None
    assert service.handle_stream_event(m, {"event": "update", "payload": "kein json"}) is None
    assert service.handle_stream_event(b, event("update", status("1"))) is None   # Bluesky: kein Stream


# -- Phase 5: Filter ------------------------------------------------------------
def test_column_options_are_stored(http, run):
    store, service, role, m, b = world(http, run)
    service.save_columns(role, [
        DeckColumnSpec(role.id, m.id, "profile", hide_boosts=True),
        DeckColumnSpec(role.id, b.id, "profile", hide_replies=True)])
    first, second = service.columns(role)
    assert (first.hide_boosts, first.hide_replies) == (True, False)
    assert (second.hide_boosts, second.hide_replies) == (False, True)


def test_server_filters_hide_or_fold():
    from dandelion.reader.mastodon import parse_status
    hidden = parse_status(status("1", filtered=[{"filter": {"title": "Politik", "filter_action": "hide"}}]))
    assert hidden.hidden
    warned = parse_status(status("2", filtered=[{"filter": {"title": "Spoiler", "filter_action": "warn"}}]))
    assert not warned.hidden and warned.sensitive and "Spoiler" in warned.spoiler
    own = parse_status(status("3", spoiler_text="Eigene Warnung",
                              filtered=[{"filter": {"title": "X", "filter_action": "warn"}}]))
    assert own.spoiler == "Eigene Warnung"


def test_reply_detection():
    from dandelion.reader.bluesky import parse_feed_item
    from dandelion.reader.mastodon import parse_status
    assert parse_status(status("1", in_reply_to_id="9", in_reply_to_account_id="42")).is_reply
    mine = status("2", in_reply_to_id="9")
    mine["in_reply_to_account_id"] = mine["account"]["id"]
    assert not parse_status(mine).is_reply                  # Thread mit sich selbst
    assert not parse_status(status("3")).is_reply
    reply = {"post": post_view(), "reply": {"parent": {"author": {"did": "did:plc:other"}}}}
    assert parse_feed_item(reply).is_reply
    own = {"post": post_view(), "reply": {"parent": {"author": {"did": "did:plc:ole"}}}}
    assert not parse_feed_item(own).is_reply
