# SPDX-License-Identifier: GPL-3.0-or-later
import json
from datetime import UTC, datetime, timedelta

from helpers import make_post, setup_world

from dandelion.core.models import PostState, TargetState
from dandelion.core.publisher import Publisher
from dandelion.core.remote_schedule import RemoteScheduler, set_server_scheduling
from dandelion.core.scheduler import Scheduler, to_utc_iso
from dandelion.net.http import Response

NOW = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


def world(http, run, minutes=60, body="Geplant", thread="off"):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "l", {"access_token": "tok"}))
    set_server_scheduling(m, True)
    store.save_profile(m)
    post = make_post(role, [m], body=body)
    post.state = PostState.SCHEDULED
    post.scheduled_at = to_utc_iso(NOW + timedelta(minutes=minutes))
    post.use_signature = False
    post.thread_mode = thread
    store.save_post(post)
    counter = {"n": 0}

    def scheduled(req):
        counter["n"] += 1
        return Response(200, {}, json.dumps({"id": f"SCH{counter['n']}",
                                             "scheduled_at": req.form["scheduled_at"]}).encode(),
                        req.url)

    http.add("POST", "https://social.example/api/v1/statuses", scheduled)
    http.add("DELETE", "https://social.example/api/v1/scheduled_statuses/", {})
    remote = RemoteScheduler(store, reg, Publisher(store, reg))
    return store, reg, remote, post, m


def target(store, post):
    return store.load_post(post.id).targets[0]


def test_schedules_on_server_and_is_idempotent(http, run):
    store, reg, remote, post, m = world(http, run)
    assert run(remote.sync_post(post.id, now=NOW)) == []
    t = target(store, post)
    assert t.state == TargetState.SCHEDULED_REMOTE and json.loads(t.remote_scheduled_id)["id"] == "SCH1"
    req = http.find("POST", "https://social.example/api/v1/statuses")[0]
    assert req.form["scheduled_at"] == post.scheduled_at
    run(remote.sync_post(post.id, now=NOW))                    # nichts geändert
    assert len(http.find("POST", "https://social.example/api/v1/statuses")) == 1


def test_change_recreates_and_pause_cancels(http, run):
    store, reg, remote, post, m = world(http, run)
    run(remote.sync_post(post.id, now=NOW))
    p = store.load_post(post.id)
    p.body = "Geänderter Text"
    store.save_post(p)
    run(remote.sync_post(post.id, now=NOW))
    assert http.find("DELETE", "https://social.example/api/v1/scheduled_statuses/SCH1")
    assert json.loads(target(store, post).remote_scheduled_id)["id"] == "SCH2"
    store.set_post_schedule(post.id, PostState.PAUSED, p.scheduled_at)
    run(remote.sync_post(post.id, now=NOW))
    assert http.find("DELETE", "https://social.example/api/v1/scheduled_statuses/SCH2")
    t = target(store, post)
    assert t.state == TargetState.PENDING and t.remote_scheduled_id is None


def test_too_soon_or_thread_stays_local(http, run):
    store, reg, remote, post, m = world(http, run, minutes=3)
    run(remote.sync_post(post.id, now=NOW))
    assert target(store, post).state == TargetState.PENDING
    store2, reg2, remote2, post2, m2 = world(http, run, body="x " * 600, thread="fraction")
    run(remote2.sync_post(post2.id, now=NOW))
    assert target(store2, post2).state == TargetState.PENDING


def test_due_post_is_resolved_not_resent(http, run):
    store, reg, remote, post, m = world(http, run)
    run(remote.sync_post(post.id, now=NOW))
    later = NOW + timedelta(minutes=61)
    http.add("GET", "https://social.example/api/v1/accounts/1/statuses", [
        {"id": "99", "url": "https://social.example/@toff/99",
         "created_at": to_utc_iso(NOW + timedelta(minutes=60, seconds=2)).replace("+00:00", "Z")}])
    result = run(Scheduler(store, Publisher(store, reg), clock=lambda: later).run_due())
    assert result.sent and result.sent[0].state == PostState.PUBLISHED
    t = target(store, post)
    assert t.state == TargetState.PUBLISHED and t.remote_url.endswith("/99")
    assert len(http.find("POST", "https://social.example/api/v1/statuses")) == 1


def test_delete_cancels_and_draft_after_due_does_not(http, run):
    store, reg, remote, post, m = world(http, run)
    run(remote.sync_post(post.id, now=NOW))
    run(remote.sync_post(post.id, deleted=True, now=NOW))
    assert http.find("DELETE", "https://social.example/api/v1/scheduled_statuses/SCH1")

    store, reg, remote, post, m = world(http, run)
    run(remote.sync_post(post.id, now=NOW))
    http.add("GET", "https://social.example/api/v1/accounts/1/statuses", [])
    store.set_post_schedule(post.id, PostState.DRAFT, post.scheduled_at)
    deletes_before = len(http.find("DELETE", "https://social.example/api/v1/scheduled_statuses/"))
    run(remote.sync_post(post.id, now=NOW + timedelta(hours=2)))
    assert target(store, post).state == TargetState.PUBLISHED
    assert len(http.find("DELETE", "https://social.example/api/v1/scheduled_statuses/")) == \
        deletes_before


def test_server_error_falls_back_to_local(http, run):
    store, reg, remote, post, m = world(http, run)
    http.add("POST", "https://social.example/api/v1/statuses",
             {"error": "Tageslimit erreicht"}, 422)
    errors = run(remote.sync_post(post.id, now=NOW))
    assert errors and "Tageslimit" in errors[0]
    assert target(store, post).state == TargetState.PENDING
