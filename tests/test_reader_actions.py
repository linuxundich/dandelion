# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from helpers import setup_world
from test_reader import status
from test_reader_bluesky import post_view, session

from dandelion.platforms.base import Composition, PlatformError
from dandelion.reader.base import FeedAccount, Relationship
from dandelion.reader.bluesky import parse_post_view
from dandelion.reader.mastodon import parse_status
from dandelion.reader.service import ReaderService

M = "https://social.example"
P = "https://pds.example/xrpc/"


def masto(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "x", {"access_token": "tok"}))
    return ReaderService(store, reg), m


def bsky(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    session(secrets, b)
    http.add("POST", P + "com.atproto.repo.createRecord", {"uri": "at://did:plc:abc/app.bsky.feed.like/3x",
                                                          "cid": "c"})
    http.add("POST", P + "com.atproto.repo.deleteRecord", {})
    return ReaderService(store, reg), b


# -- Zustände parsen ---------------------------------------------------------
def test_mastodon_state_and_ref_for_boost():
    original = status("55", favourited=True, reblogged=False, bookmarked=True, visibility="unlisted")
    boost = parse_status({"id": "200", "created_at": "2026-11-11T11:00:00.000Z",
                          "account": original["account"], "reblog": original, "content": ""})
    assert boost.id == "200" and boost.ref == "55"          # handeln auf dem Original
    assert boost.favourited and boost.bookmarked and not boost.boosted
    assert boost.visibility == "unlisted"


def test_bluesky_state_and_thread_root():
    view = post_view(viewer={"like": "at://me/app.bsky.feed.like/1", "repost": None,
                             "bookmarked": True},
                     record={"text": "x", "createdAt": "2026-11-11T10:00:00Z",
                             "reply": {"root": {"uri": "at://r/app.bsky.feed.post/1", "cid": "rc"},
                                       "parent": {"uri": "at://p/app.bsky.feed.post/2", "cid": "pc"}}})
    view["cid"] = "pcid"
    post = parse_post_view(view)
    assert post.ref == view["uri"] and post.cid == "pcid"
    assert post.favourited and not post.boosted and post.bookmarked
    assert post.like_uri == "at://me/app.bsky.feed.like/1"
    assert post.root_ref == ("at://r/app.bsky.feed.post/1", "rc")


# -- Mastodon ----------------------------------------------------------------
@pytest.mark.parametrize("action,path", [
    ("favourite", "favourite"), ("unfavourite", "unfavourite"), ("boost", "reblog"),
    ("unboost", "unreblog"), ("bookmark", "bookmark"), ("unbookmark", "unbookmark")])
def test_mastodon_actions(http, run, action, path):
    service, m = masto(http, run)
    http.add("POST", f"{M}/api/v1/statuses/55/{path}", status("55"))
    post = parse_status(status("55"))
    run(service.act(m, post, action))
    req = http.find("POST", f"{M}/api/v1/statuses/55/{path}")[0]
    assert req.headers["Authorization"] == "Bearer tok"


def test_mastodon_action_failure_raises(http, run):
    service, m = masto(http, run)
    http.add("POST", f"{M}/api/v1/statuses/55/favourite", {"error": "Record not found"}, status=404)
    with pytest.raises(PlatformError):
        run(service.act(m, parse_status(status("55")), "favourite"))


def test_mastodon_relationship(http, run):
    service, m = masto(http, run)
    account = FeedAccount("7", "mara", "Mara")
    http.add("GET", f"{M}/api/v1/accounts/relationships",
             [{"id": "7", "following": True, "followed_by": False, "muting": False,
               "blocking": False, "requested": False}])
    rel = run(service.relationship(m, account))
    assert rel.following and not rel.muted
    assert "id%5B%5D=7" in http.find("GET", f"{M}/api/v1/accounts/relationships")[0].full_url()
    http.add("POST", f"{M}/api/v1/accounts/7/mute", {"id": "7", "following": True, "muting": True})
    rel = run(service.set_relationship(m, account, "mute", rel))
    assert rel.muted and rel.following


def test_mastodon_reply_sends_parent(http, run):
    service, m = masto(http, run)
    http.add("POST", f"{M}/api/v1/statuses", {"id": "900", "url": "https://x/900"})
    parent = parse_status(status("55"))
    part = run(service.send(m, Composition("@mara Danke", visibility="unlisted"), reply_to=parent))
    form = http.find("POST", f"{M}/api/v1/statuses")[0].form
    assert form["in_reply_to_id"] == "55" and form["visibility"] == "unlisted"
    assert part.remote_id == "900"


def test_mastodon_has_no_quote(http, run):
    service, m = masto(http, run)
    assert not service.can_quote(m)
    with pytest.raises(PlatformError):
        run(service.send(m, Composition("x"), quote=parse_status(status("55"))))


# -- Bluesky -----------------------------------------------------------------
def test_bluesky_like_and_unlike(http, run):
    service, b = bsky(http, run)
    post = parse_post_view(dict(post_view(), cid="pcid"))
    run(service.act(b, post, "favourite"))
    body = http.find("POST", P + "com.atproto.repo.createRecord")[0].json
    assert body["collection"] == "app.bsky.feed.like" and body["repo"] == "did:plc:abc"
    assert body["record"]["subject"] == {"uri": post.ref, "cid": "pcid"}
    assert post.like_uri == "at://did:plc:abc/app.bsky.feed.like/3x"
    run(service.act(b, post, "unfavourite"))
    body = http.find("POST", P + "com.atproto.repo.deleteRecord")[0].json
    assert body["collection"] == "app.bsky.feed.like" and body["rkey"] == "3x"
    assert post.like_uri is None


def test_bluesky_repost_and_bookmark(http, run):
    service, b = bsky(http, run)
    http.add("POST", P + "app.bsky.bookmark.createBookmark", {})
    http.add("POST", P + "app.bsky.bookmark.deleteBookmark", {})
    post = parse_post_view(dict(post_view(), cid="pcid"))
    run(service.act(b, post, "boost"))
    assert http.find("POST", P + "com.atproto.repo.createRecord")[0].json["collection"] == \
        "app.bsky.feed.repost"
    run(service.act(b, post, "bookmark"))
    assert http.find("POST", P + "app.bsky.bookmark.createBookmark")[0].json == \
        {"uri": post.ref, "cid": "pcid"}
    run(service.act(b, post, "unbookmark"))
    assert http.find("POST", P + "app.bsky.bookmark.deleteBookmark")[0].json == {"uri": post.ref}


def test_bluesky_relationships(http, run):
    service, b = bsky(http, run)
    account = FeedAccount("did:plc:ole", "ole.bsky.social", "Ole")
    http.add("GET", P + "app.bsky.actor.getProfile",
             {"viewer": {"following": "at://me/app.bsky.graph.follow/9", "muted": False}})
    rel = run(service.relationship(b, account))
    assert rel.following and rel.follow_uri.endswith("/9")
    rel = run(service.set_relationship(b, account, "unfollow", rel))
    assert not rel.following
    assert http.find("POST", P + "com.atproto.repo.deleteRecord")[0].json["rkey"] == "9"
    rel = run(service.set_relationship(b, account, "follow", rel))
    assert rel.following and rel.follow_uri
    http.add("POST", P + "app.bsky.graph.muteActor", {})
    rel = run(service.set_relationship(b, account, "mute", rel))
    assert rel.muted and http.find("POST", P + "app.bsky.graph.muteActor")[0].json == \
        {"actor": "did:plc:ole"}
    rel = run(service.set_relationship(b, account, "block", Relationship()))
    assert rel.blocking and rel.block_uri


def test_bluesky_reply_and_quote(http, run):
    service, b = bsky(http, run)
    http.add("GET", "https://pds.example/xrpc/com.atproto.identity.resolveHandle", {"did": "d"})
    view = dict(post_view(), cid="pcid", record={
        "text": "x", "createdAt": "2026-11-11T10:00:00Z",
        "reply": {"root": {"uri": "at://r/app.bsky.feed.post/1", "cid": "rc"},
                  "parent": {"uri": "at://r/app.bsky.feed.post/1", "cid": "rc"}}})
    target = parse_post_view(view)
    run(service.send(b, Composition("Stimmt"), reply_to=target))
    rec = http.find("POST", P + "com.atproto.repo.createRecord")[0].json["record"]
    assert rec["reply"]["parent"] == {"uri": target.ref, "cid": "pcid"}
    assert rec["reply"]["root"] == {"uri": "at://r/app.bsky.feed.post/1", "cid": "rc"}
    assert service.can_quote(b)
    run(service.send(b, Composition("Lesenswert"), quote=target))
    rec = http.find("POST", P + "com.atproto.repo.createRecord")[1].json["record"]
    assert rec["embed"] == {"$type": "app.bsky.embed.record",
                            "record": {"uri": target.ref, "cid": "pcid"}}


def test_action_patches_the_cache(http, run):
    service, m = masto(http, run)
    first = [status("30", created_at="2026-11-11T10:03:00.000Z", favourites_count=2)]
    http.add("GET", f"{M}/api/v1/timelines/home", first)
    http.add("GET", f"{M}/api/v1/markers", {})
    http.add("POST", f"{M}/api/v1/statuses/30/favourite", status("30"))
    post = run(service.refresh(m, "home"))[0]
    post.favourited, post.likes = True, 3                  # was die Oberfläche sofort tut
    run(service.act(m, post, "favourite", "home"))
    cached = service.cached(m, "home")[0]
    assert cached.favourited and cached.likes == 3
