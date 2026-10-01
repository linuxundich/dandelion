# SPDX-License-Identifier: GPL-3.0-or-later
import time

import pytest
from helpers import make_post, setup_world
from test_platforms import jwt

from dandelion.core.models import PostState, TargetState
from dandelion.core.publisher import AlreadySending, Publisher


def prepare(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "l", {"access_token": "tok"}))
    run(secrets.set(b.uuid, "app-password", "l", {
        "pds": "https://pds.example", "did": "did:plc:abc", "app_password": "pw",
        "access_jwt": jwt(time.time() + 3600), "refresh_jwt": "r"}))
    post = store.save_post(make_post(role, [m, b]))
    return store, reg, post, m, b


def test_partial_failure_and_retry(http, run):
    store, reg, post, m, b = prepare(http, run)
    http.add("POST", "https://social.example/api/v1/statuses", {"id": "1", "url": "https://m/1"})
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"error": "InvalidRequest", "message": "kaputt"}, 400)
    events = []
    pub = Publisher(store, reg)
    result = run(pub.send(post.id, on_update=lambda p, t, s: events.append(s)))
    assert result.state == PostState.PARTIAL
    states = {t.profile_id: t.state for t in store.load_post(post.id).targets}
    assert states == {m.id: TargetState.PUBLISHED, b.id: TargetState.FAILED}
    assert "published" in events and "failed" in events

    # Nur Bluesky erneut senden, Mastodon darf nicht doppelt posten
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"uri": "at://did:plc:abc/app.bsky.feed.post/9", "cid": "c"})
    result = run(pub.send(post.id))
    assert result.state == PostState.PUBLISHED
    assert len(http.find("POST", "https://social.example/api/v1/statuses")) == 1


def test_signature_appended(http, run):
    store, reg, post, m, b = prepare(http, run)
    http.add("POST", "https://social.example/api/v1/statuses", {"id": "1", "url": "u"})
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"uri": "at://x/app.bsky.feed.post/1", "cid": "c"})
    run(Publisher(store, reg).send(post.id))
    assert http.find("POST", "https://social.example/api/v1/statuses")[0].form["status"] == \
        "Hallo Welt\n\n#linux"


def test_claim_prevents_double_send(http, run):
    store, reg, post, m, b = prepare(http, run)
    assert store.claim_post(post.id, "2999-01-01T00:00:00+00:00", [PostState.DRAFT])
    with pytest.raises(AlreadySending):
        run(Publisher(store, reg).send(post.id))


def test_network_error_retries_then_fails(http, run, monkeypatch):
    import dandelion.core.publisher as pubmod
    monkeypatch.setattr(pubmod, "RETRY_DELAYS", (0.0,))
    store, reg, post, m, b = prepare(http, run)
    http.fail("POST", "https://social.example/api/v1/statuses")
    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord",
             {"uri": "at://x/app.bsky.feed.post/1", "cid": "c"})
    result = run(Publisher(store, reg).send(post.id))
    assert result.state == PostState.PARTIAL
    assert len(http.find("POST", "https://social.example/api/v1/statuses")) == 2
    t = next(t for t in store.load_post(post.id).targets if t.profile_id == m.id)
    assert "internet" in t.last_error.lower()
