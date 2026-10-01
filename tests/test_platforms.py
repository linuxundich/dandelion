# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import json
import time

import pytest
from helpers import setup_world

from dandelion.core.models import TargetPart
from dandelion.platforms.base import Composition, PlatformError
from dandelion.platforms.bluesky import Bluesky, normalize_handle
from dandelion.platforms.mastodon import Mastodon, normalize_instance


def jwt(exp):
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode().rstrip("=")
    return f"x.{payload}.y"


def test_normalize():
    assert normalize_instance("https://Social.Tchncs.de/about") == "social.tchncs.de"
    assert normalize_instance("@toff@social.tchncs.de") == "social.tchncs.de"
    assert normalize_handle("@Lui") == "lui.bsky.social"
    assert normalize_handle("linuxundich.de") == "linuxundich.de"


def test_mastodon_login_flow(http, run):
    store, secrets, reg, *_ = setup_world(http)
    mastodon: Mastodon = reg.get("mastodon")
    http.add("POST", "https://social.example/api/v1/apps", {"client_id": "cid", "client_secret": "cs"})
    http.add("POST", "https://social.example/oauth/token", {"access_token": "tok"})
    http.add("GET", "https://social.example/api/v1/accounts/verify_credentials",
             {"id": "42", "username": "toff", "display_name": "Christoph", "avatar_static": "a.png"})
    pending = run(mastodon.begin_login("social.example", "http://127.0.0.1:5000/callback"))
    assert "code_challenge=" in pending.authorize_url()
    profile, secret = run(mastodon.finish_login(pending, "CODE", pending.redirect_uri))
    assert profile.handle == "toff" and secret["access_token"] == "tok"
    token_req = http.find("POST", "https://social.example/oauth/token")[0]
    assert token_req.form["code_verifier"] == pending.pkce.verifier


def test_mastodon_instance_limits(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    http.add("GET", "https://social.example/api/v2/instance", {"configuration": {
        "statuses": {"max_characters": 1000, "characters_reserved_per_url": 23,
                     "max_media_attachments": 6},
        "media_attachments": {"description_limit": 1500, "image_size_limit": 10485760}}})
    limits = run(reg.get("mastodon").fetch_limits(m))
    assert (limits.max_chars, limits.max_images, limits.max_image_bytes) == (1000, 6, 10485760)


def test_mastodon_post(http, run, tmp_path):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "l", {"access_token": "tok"}))
    http.add("POST", "https://social.example/api/v1/statuses",
             {"id": "99", "url": "https://social.example/@toff/99"})
    part = run(reg.get("mastodon").post(m, Composition("Hallo", content_warning="CW",
                                                       visibility="unlisted"), [],
                                        reply_to=None, root=None, idempotency_key="k1"))
    assert part.remote_url.endswith("/99")
    req = http.find("POST", "https://social.example/api/v1/statuses")[0]
    assert req.headers["Idempotency-Key"] == "k1"
    assert req.headers["Authorization"] == "Bearer tok"
    assert req.form["spoiler_text"] == "CW" and req.form["visibility"] == "unlisted"


def test_mastodon_errors(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "l", {"access_token": "tok"}))
    http.add("POST", "https://social.example/api/v1/statuses", {"error": "Text too long"}, 422)
    with pytest.raises(PlatformError) as e:
        run(reg.get("mastodon").post(m, Composition("x"), [], reply_to=None, root=None,
                                     idempotency_key="k"))
    assert "Text too long" in e.value.message and not e.value.retryable
    http.fail("POST", "https://social.example/api/v1/statuses")
    with pytest.raises(PlatformError) as e:
        run(reg.get("mastodon").post(m, Composition("x"), [], reply_to=None, root=None,
                                     idempotency_key="k"))
    assert e.value.retryable


def bsky_routes(http):
    http.add("GET", "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle",
             {"did": "did:plc:abc"})
    http.add("GET", "https://plc.directory/did:plc:abc", {"service": [
        {"id": "#atproto_pds", "type": "AtprotoPersonalDataServer",
         "serviceEndpoint": "https://pds.example"}]})
    http.add("POST", "https://pds.example/xrpc/com.atproto.server.createSession",
             {"accessJwt": jwt(time.time() + 3600), "refreshJwt": "r", "handle": "lui.bsky.social",
              "did": "did:plc:abc"})
    http.add("GET", "https://pds.example/xrpc/app.bsky.actor.getProfile",
             {"handle": "lui.bsky.social", "displayName": "Lui", "avatar": "https://a"})


def test_bluesky_login(http, run):
    store, secrets, reg, *_ = setup_world(http)
    bsky_routes(http)
    profile, secret = run(reg.get("bluesky").login_app_password("lui", "abcd-efgh"))
    assert profile.remote_id == "did:plc:abc" and profile.display_name == "Lui"
    assert secret["pds"] == "https://pds.example" and secret["app_password"] == "abcd-efgh"


def test_bluesky_post_with_facets_and_card(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    bsky_routes(http)
    run(secrets.set(b.uuid, "app-password", "l", {
        "pds": "https://pds.example", "did": "did:plc:abc", "app_password": "pw",
        "access_jwt": jwt(time.time() + 3600), "refresh_jwt": "r"}))
    http.add("GET", "https://linuxundich.de/", raw=b'<html><head><meta property="og:title" '
             b'content="GNOME 50"><meta property="og:description" content="Test"></head></html>',
             headers={"content-type": "text/html"})
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"uri": "at://did:plc:abc/app.bsky.feed.post/3k", "cid": "bafy"})
    text = "Grüße @linuxundich.de 👋 https://linuxundich.de/2026/10/gnome-50-test #GNOME"
    part = run(reg.get("bluesky").post(b, Composition(text, language="de"), [],
                                       reply_to=None, root=None, idempotency_key="k"))
    assert part.remote_url == "https://bsky.app/profile/lui.bsky.social/post/3k"
    record = http.find("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord")[0] \
        .json["record"]
    assert "linuxundich.de/2026/10/gnom..." in record["text"]
    kinds = [f["features"][0]["$type"].rsplit("#", 1)[1] for f in record["facets"]]
    assert kinds == ["mention", "link", "tag"]
    raw = record["text"].encode()
    link = record["facets"][1]
    assert raw[link["index"]["byteStart"]:link["index"]["byteEnd"]].decode() == \
        "linuxundich.de/2026/10/gnom..."
    assert link["features"][0]["uri"] == "https://linuxundich.de/2026/10/gnome-50-test"
    assert record["langs"] == ["de"]


def test_bluesky_refresh_falls_back_to_app_password(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    bsky_routes(http)
    run(secrets.set(b.uuid, "app-password", "l", {
        "pds": "https://pds.example", "did": "did:plc:abc", "app_password": "pw",
        "access_jwt": jwt(time.time() - 10), "refresh_jwt": "old"}))
    http.add("POST", "https://pds.example/xrpc/com.atproto.server.refreshSession",
             {"error": "ExpiredToken", "message": "expired"}, 400)
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"uri": "at://did:plc:abc/app.bsky.feed.post/1", "cid": "c"})
    run(reg.get("bluesky").post(b, Composition("hi"), [], reply_to=None, root=None,
                                idempotency_key="k"))
    assert http.find("POST", "https://pds.example/xrpc/com.atproto.server.createSession")
    assert run(secrets.get(b.uuid, "app-password"))["refresh_jwt"] == "r"


def test_bluesky_reply_refs(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(b.uuid, "app-password", "l", {
        "pds": "https://pds.example", "did": "did:plc:abc", "app_password": "pw",
        "access_jwt": jwt(time.time() + 3600), "refresh_jwt": "r"}))
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"uri": "at://x/app.bsky.feed.post/2", "cid": "c2"})
    parent = TargetPart(0, "at://x/app.bsky.feed.post/1", "c1")
    run(reg.get("bluesky").post(b, Composition("teil 2"), [], reply_to=parent, root=parent,
                                idempotency_key="k"))
    rec = http.requests[-1].json["record"]
    assert rec["reply"]["parent"]["cid"] == "c1" and rec["reply"]["root"]["uri"].endswith("/1")
