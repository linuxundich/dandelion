# SPDX-License-Identifier: GPL-3.0-or-later
import time

from helpers import setup_world
from test_platforms import jwt

from dandelion.reader.base import HOME, NOTIFICATIONS
from dandelion.reader.bluesky import facets_markup, parse_feed_item, parse_notification
from dandelion.reader.service import ReaderService

AUTHOR = {"did": "did:plc:ole", "handle": "ole.bsky.social", "displayName": "Ole Brandt",
          "avatar": "https://cdn/a.jpg"}


def post_view(uri="at://did:plc:ole/app.bsky.feed.post/3k1", text="Hallo #welt", **kw):
    base = {"uri": uri, "cid": "c", "author": AUTHOR,
            "record": {"text": text, "createdAt": "2026-11-11T10:00:00.000Z",
                       "langs": ["de"], "facets": [
                           {"index": {"byteStart": 6, "byteEnd": 11},
                            "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": "welt"}]}
                       ] if text == "Hallo #welt" else []},
            "replyCount": 1, "repostCount": 2, "likeCount": 3, "indexedAt": "2026-11-11T10:00:01.000Z"}
    base.update(kw)
    return base


def test_facets_markup_uses_utf8_byte_offsets():
    text = "Grüße an bsky.app ok"
    start = len("Grüße an ".encode())
    out = facets_markup(text, [{"index": {"byteStart": start, "byteEnd": start + 8},
                                "features": [{"$type": "app.bsky.richtext.facet#link",
                                              "uri": "https://bsky.app/"}]}])
    assert out == 'Grüße an <a href="https://bsky.app/">bsky.app</a> ok'


def test_facets_markup_escapes_and_ignores_bad_facets():
    out = facets_markup("a < b & c", [{"index": {"byteStart": 50, "byteEnd": 60},
                                       "features": [{"$type": "x#link", "uri": "https://a/"}]},
                                      {"index": {"byteStart": 0, "byteEnd": 1},
                                       "features": [{"$type": "x#link", "uri": "javascript:x"}]}])
    assert out == "a &lt; b &amp; c"


def test_parse_post_with_embeds_and_repost():
    view = post_view(embed={
        "$type": "app.bsky.embed.recordWithMedia#view",
        "media": {"$type": "app.bsky.embed.images#view", "images": [
            {"thumb": "https://cdn/t.jpg", "fullsize": "https://cdn/f.jpg", "alt": "Ein Bild"}]},
        "record": {"record": {"$type": "app.bsky.embed.record#viewRecord", "uri": "at://x/app.bsky.feed.post/9",
                              "author": dict(AUTHOR, handle="flathub.org", displayName="Flathub"),
                              "value": {"text": "212 Updates", "createdAt": "2026-11-10T10:00:00Z"}}}})
    raw = {"post": view, "reason": {"$type": "app.bsky.feed.defs#reasonRepost",
                                    "by": dict(AUTHOR, did="did:plc:mara", displayName="Mara"),
                                    "indexedAt": "2026-11-11T11:00:00.000Z"}}
    post = parse_feed_item(raw)
    assert post.boosted_by.name == "Mara" and post.id.endswith("|did:plc:mara")
    assert post.created_at == "2026-11-11T11:00:00.000Z"
    assert post.media[0].alt == "Ein Bild" and post.media[0].preview_url == "https://cdn/t.jpg"
    assert post.quote.account.name == "Flathub" and "212" in post.quote.markup
    assert '<a href="https://bsky.app/hashtag/welt">#welt</a>' in post.markup
    assert (post.replies, post.boosts, post.likes) == (1, 2, 3) and post.language == "de"
    assert post.url == "https://bsky.app/profile/ole.bsky.social/post/3k1"


def test_parse_external_card_and_label():
    post = parse_feed_item({"post": post_view(
        embed={"$type": "app.bsky.embed.external#view",
               "external": {"uri": "https://l/", "title": "Titel", "description": "d", "thumb": "t"}},
        labels=[{"val": "graphic-media"}])})
    assert post.card.title == "Titel" and post.sensitive and "graphic media" in post.spoiler


def test_parse_notifications():
    fav = parse_notification({"uri": "at://n/1", "reason": "like", "author": AUTHOR,
                              "reasonSubject": "at://s/app.bsky.feed.post/1",
                              "indexedAt": "2026-11-11T10:00:00Z", "record": {}},
                             {"at://s/app.bsky.feed.post/1": post_view(text="Mein Beitrag")})
    assert fav.reason == "favourite" and "Mein Beitrag" in fav.subject.markup
    reply = parse_notification({"uri": "at://n/2", "reason": "reply", "author": AUTHOR,
                                "indexedAt": "2026-11-11T10:00:00Z",
                                "record": {"text": "Stimmt!", "embed": {"images": [{"alt": "x"}]}}}, {})
    assert reply.reason == "reply" and reply.markup == "Stimmt!" and len(reply.media) == 1


def session(secrets, profile):
    import asyncio
    asyncio.run(secrets.set(profile.uuid, "app-password", "x", {
        "access_jwt": jwt(time.time() + 3600), "refresh_jwt": "r", "pds": "https://pds.example",
        "did": "did:plc:abc", "app_password": "pw"}))


def test_home_paging_with_cursor(http, run):
    store, secrets, reg, role, masto, bsky = setup_world(http)
    session(secrets, bsky)
    import json

    from dandelion.net.http import Response

    def timeline(req):
        if "cursor=c1" in req.full_url():
            data = {"feed": [{"post": post_view("at://x/app.bsky.feed.post/old",
                                                indexedAt="2026-11-11T09:00:00.000Z")}]}
        else:
            data = {"cursor": "c1", "feed": [{"post": post_view("at://x/app.bsky.feed.post/new")}]}
        return Response(200, {"content-type": "application/json"}, json.dumps(data).encode(),
                        req.full_url())
    http.add("GET", "https://pds.example/xrpc/app.bsky.feed.getTimeline", timeline)
    service = ReaderService(store, reg)
    assert service.feeds(bsky) == (HOME, NOTIFICATIONS)
    assert len(run(service.refresh(bsky, HOME))) == 1
    assert service.unread(bsky, HOME) == 0          # Erstabruf: alles gilt als gelesen
    older = run(service.load_older(bsky, HOME))
    assert [p.id for p in older] == ["at://x/app.bsky.feed.post/new", "at://x/app.bsky.feed.post/old"]


def test_notifications_fetch_subjects_and_mark_seen(http, run):
    store, secrets, reg, role, masto, bsky = setup_world(http)
    session(secrets, bsky)
    http.add("GET", "https://pds.example/xrpc/app.bsky.notification.listNotifications", {
        "notifications": [{"uri": "at://n/1", "reason": "like", "author": AUTHOR,
                           "reasonSubject": "at://s/app.bsky.feed.post/1",
                           "indexedAt": "2026-11-11T10:00:00Z", "record": {}}]})
    http.add("GET", "https://pds.example/xrpc/app.bsky.feed.getPosts",
             {"posts": [post_view("at://s/app.bsky.feed.post/1", text="Mein Beitrag")]})
    http.add("POST", "https://pds.example/xrpc/app.bsky.notification.updateSeen", {})
    service = ReaderService(store, reg)
    items = run(service.refresh(bsky, NOTIFICATIONS))
    assert items[0].reason == "favourite" and "Mein Beitrag" in items[0].subject.markup
    # nach einem Neustart steht das Ziel noch im Cache, ohne neue Anfrage
    assert "Mein Beitrag" in service.cached(bsky, NOTIFICATIONS)[0].subject.markup
    run(service.mark_read(bsky, NOTIFICATIONS))
    assert http.find("POST", "https://pds.example/xrpc/app.bsky.notification.updateSeen")
