# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from helpers import make_post, setup_world

from dandelion.core.models import PostState
from dandelion.core.publisher import Publisher
from dandelion.core.scheduler import MissedPolicy, Scheduler, to_utc_iso
from dandelion.core.store import PostLocked
from dandelion.core.trigger import calendar_spec, dropin_text, service_text

NOW = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def world(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    run(secrets.set(m.uuid, "oauth", "l", {"access_token": "tok"}))
    http.add("POST", "https://social.example/api/v1/statuses", {"id": "1", "url": "https://m/1"})
    return store, reg, role, m


def schedule(store, role, m, when, state=PostState.SCHEDULED):
    post = make_post(role, [m])
    post.state = state
    post.scheduled_at = to_utc_iso(when)
    return store.save_post(post)


def test_due_post_is_sent(http, run):
    store, reg, role, m = world(http, run)
    post = schedule(store, role, m, NOW - timedelta(minutes=1))
    later = schedule(store, role, m, NOW + timedelta(hours=2))
    sched = Scheduler(store, Publisher(store, reg), clock=Clock(NOW))
    result = run(sched.run_due())
    assert [p.id for p in result.sent] == [post.id]
    assert store.post_state(post.id) == PostState.PUBLISHED
    assert store.post_state(later.id) == PostState.SCHEDULED
    assert result.next_due == NOW + timedelta(hours=2)


def test_future_and_paused_not_sent(http, run):
    store, reg, role, m = world(http, run)
    schedule(store, role, m, NOW + timedelta(seconds=30))
    paused = schedule(store, role, m, NOW - timedelta(minutes=5), PostState.PAUSED)
    result = run(Scheduler(store, Publisher(store, reg), clock=Clock(NOW)).run_due())
    assert not result.sent and not result.missed
    assert store.post_state(paused.id) == PostState.PAUSED
    assert not http.find("POST", "https://social.example/api/v1/statuses")


@pytest.mark.parametrize("policy, sent, missed", [
    (MissedPolicy.ASK, 0, 1),
    (MissedPolicy.DISCARD, 0, 1),
    (MissedPolicy.SEND, 1, 0),
])
def test_missed_policy(http, run, policy, sent, missed):
    store, reg, role, m = world(http, run)
    post = schedule(store, role, m, NOW - timedelta(hours=3))   # z. B. nach Suspend
    sched = Scheduler(store, Publisher(store, reg), policy=policy,
                      grace=timedelta(minutes=15), clock=Clock(NOW))
    result = run(sched.run_due())
    assert len(result.late) == sent and len(result.missed) == missed
    expected = PostState.PUBLISHED if sent else PostState.MISSED
    assert store.post_state(post.id) == expected
    if missed:
        assert [p.id for p in sched.missed_posts()] == [post.id]


def test_within_grace_is_sent_normally(http, run):
    store, reg, role, m = world(http, run)
    schedule(store, role, m, NOW - timedelta(minutes=10))
    result = run(Scheduler(store, Publisher(store, reg), grace=timedelta(minutes=15),
                           clock=Clock(NOW)).run_due())
    assert len(result.sent) == 1 and not result.late


def test_second_run_does_not_resend(http, run):
    store, reg, role, m = world(http, run)
    schedule(store, role, m, NOW - timedelta(minutes=1))
    sched = Scheduler(store, Publisher(store, reg), clock=Clock(NOW))
    run(sched.run_due())
    run(sched.run_due())
    assert len(http.find("POST", "https://social.example/api/v1/statuses")) == 1


def test_claimed_post_is_skipped(http, run):
    store, reg, role, m = world(http, run)
    post = schedule(store, role, m, NOW - timedelta(minutes=1))
    assert store.claim_post(post.id, "2999-01-01T00:00:00+00:00", [PostState.SCHEDULED])
    result = run(Scheduler(store, Publisher(store, reg), clock=Clock(NOW)).run_due())
    assert not result.sent


def test_guarded_save_after_publish(http, run):
    store, reg, role, m = world(http, run)
    post = schedule(store, role, m, NOW - timedelta(minutes=1))
    run(Scheduler(store, Publisher(store, reg), clock=Clock(NOW)).run_due())
    post.state = PostState.SCHEDULED          # veraltete Kopie im Composer
    with pytest.raises(PostLocked):
        store.save_post(post, guard_editable=True)
    assert store.post_state(post.id) == PostState.PUBLISHED


def test_dst_change_is_unambiguous():
    berlin = ZoneInfo("Europe/Berlin")
    # 25.10.2026, 02:30 gibt es in Berlin zweimal; fold unterscheidet sie
    first = datetime(2026, 10, 25, 2, 30, tzinfo=berlin, fold=0)
    second = datetime(2026, 10, 25, 2, 30, tzinfo=berlin, fold=1)
    assert calendar_spec(first) == "2026-10-25 00:30:00 UTC"
    assert calendar_spec(second) == "2026-10-25 01:30:00 UTC"
    assert to_utc_iso(first) < to_utc_iso(second)


def test_unit_texts():
    text = dropin_text(datetime(2026, 10, 2, 8, 0, tzinfo=ZoneInfo("Europe/Berlin")))
    assert "OnCalendar=\nOnCalendar=2026-10-02 06:00:00 UTC" in text
    svc = service_text("/usr/bin/dandelion", {"XDG_DATA_HOME": "/tmp/x"})
    assert "ExecStart=/usr/bin/dandelion --run-due" in svc
    assert "Environment=XDG_DATA_HOME=/tmp/x" in svc
    assert "Type=oneshot" in svc
