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


def test_thread_mastodon_chain_and_resume(http, run):
    import json as _json

    from dandelion.net.http import Response
    store, reg, post, m, b = prepare(http, run)
    post = store.load_post(post.id)
    post.body = "\n\n".join(["Absatz " + str(i) + " " + "x" * 280 for i in range(3)])
    post.thread_mode = "fraction"
    post.use_signature = False
    post.targets = [t for t in post.targets if t.profile_id == m.id]
    store.save_post(post)
    calls = {"n": 0}

    def status(req):
        calls["n"] += 1
        if calls["n"] == 2 and not getattr(status, "failed", False):
            status.failed = True
            return Response(503, {}, b'{"error":"down"}', req.url)
        return Response(200, {}, _json.dumps({"id": f"S{calls['n']}",
                                              "url": f"https://m/{calls['n']}"}).encode(), req.url)

    http.add("POST", "https://social.example/api/v1/statuses", status)
    import dandelion.core.publisher as pubmod
    pubmod.RETRY_DELAYS = ()
    result = run(Publisher(store, reg).send(post.id))
    assert result.state == PostState.FAILED
    saved = store.load_post(post.id).targets[0]
    assert [p.remote_id for p in saved.parts] == ["S1"]       # Teil 1 gesichert

    result = run(Publisher(store, reg).send(post.id))          # erneut: ab Teil 2
    assert result.state == PostState.PUBLISHED
    reqs = http.find("POST", "https://social.example/api/v1/statuses")
    forms = [r.form for r in reqs]
    assert forms[0]["status"].endswith("1/3") and forms[0]["in_reply_to_id"] is None
    assert forms[-2]["in_reply_to_id"] == "S1" and forms[-2]["status"].endswith("2/3")
    assert forms[-1]["in_reply_to_id"] == "S3"
    assert reqs[-1].headers["Idempotency-Key"].endswith("-2")
    pubmod.RETRY_DELAYS = (3.0,)


def test_thread_bluesky_root_and_parent(http, run):
    import json as _json

    from dandelion.net.http import Response
    store, reg, post, m, b = prepare(http, run)
    post = store.load_post(post.id)
    post.body = " ".join(f"Satz {i} mit Inhalt." for i in range(40))
    post.thread_mode = "plain"
    post.use_signature = False
    post.targets = [t for t in post.targets if t.profile_id == b.id]
    store.save_post(post)
    n = {"i": 0}

    def record(req):
        n["i"] += 1
        return Response(200, {}, _json.dumps({"uri": f"at://x/app.bsky.feed.post/{n['i']}",
                                              "cid": f"c{n['i']}"}).encode(), req.url)

    http.add("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord", record)
    result = run(Publisher(store, reg).send(post.id))
    assert result.state == PostState.PUBLISHED
    recs = [r.json["record"] for r in
            http.find("POST", "https://pds.example/xrpc/com.atproto.repo.createRecord")]
    assert len(recs) >= 2 and "reply" not in recs[0]
    assert recs[1]["reply"]["root"]["cid"] == "c1" and recs[1]["reply"]["parent"]["cid"] == "c1"
    if len(recs) > 2:
        assert recs[2]["reply"]["root"]["cid"] == "c1" and recs[2]["reply"]["parent"]["cid"] == "c2"
    assert all(len(r["text"]) <= 300 for r in recs)


def test_thread_validation_uses_longest_part(http, run):
    from dandelion.core.validation import validate
    store, reg, post, m, b = prepare(http, run)
    post = store.load_post(post.id)
    post.body = "x " * 600
    post.use_signature = False
    rep = validate(post, None, [m, b], reg)
    assert not rep.can_send
    post.thread_mode = "fraction"
    rep = validate(post, None, [m, b], reg)
    assert rep.can_send
    bsky = next(t for t in rep.targets if t.profile.platform == "bluesky")
    assert len(bsky.parts) >= 4 and bsky.count.used <= 300
