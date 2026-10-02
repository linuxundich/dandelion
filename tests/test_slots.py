# SPDX-License-Identifier: GPL-3.0-or-later
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from helpers import setup_world

from dandelion.core.models import Post, PostState, Role
from dandelion.core.scheduler import to_utc_iso
from dandelion.core.slots import next_free_slot, slot_times
from dandelion.core.store import Store

BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 2, 9, 30, tzinfo=BERLIN)          # Freitag


def test_slot_times():
    slots = [[0, "08:00"], [4, "18:00"]]                      # Montag 8 Uhr, Freitag 18 Uhr
    times = slot_times(slots, NOW, days=7)
    assert times[0] == datetime(2026, 10, 2, 18, 0, tzinfo=BERLIN)
    assert times[1] == datetime(2026, 10, 5, 8, 0, tzinfo=BERLIN)


def test_next_free_slot_skips_taken():
    slots = [[4, "18:00"], [0, "08:00"]]
    taken = [datetime(2026, 10, 2, 18, 0, tzinfo=BERLIN)]
    assert next_free_slot(slots, taken, NOW) == datetime(2026, 10, 5, 8, 0, tzinfo=BERLIN)
    assert next_free_slot([], [], NOW) is None


def test_slot_over_dst_change_keeps_wall_time():
    sunday_slot = [[6, "10:00"]]
    when = next_free_slot(sunday_slot, [], datetime(2026, 10, 24, 12, 0, tzinfo=BERLIN))
    assert when.hour == 10 and when.utcoffset() == timedelta(hours=1)   # Winterzeit


def test_role_slots_persist_and_migration(http, tmp_path):
    store = Store(tmp_path / "db.sqlite")
    role = store.save_role(Role("Blog", slots=[[0, "08:00"], [3, "12:30"]]))
    store.close()
    store = Store(tmp_path / "db.sqlite")
    assert store.role(role.id).slots == [[0, "08:00"], [3, "12:30"]]
    store.save_post(Post(role_id=role.id, state=PostState.SCHEDULED,
                         scheduled_at=to_utc_iso(NOW + timedelta(days=3))))
    assert len(store.scheduled_times(role.id)) == 1


def test_migration_from_v1(tmp_path):
    import sqlite3
    path = tmp_path / "old.sqlite"
    from dandelion.core import store as store_mod
    db = sqlite3.connect(path)
    buf = ""
    for line in store_mod._MIGRATIONS[1].splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            db.execute(buf)
            buf = ""
    db.execute("PRAGMA user_version = 1")
    db.execute("INSERT INTO role (uuid,name,position,created_at,updated_at) VALUES ('u','Alt',0,'x','x')")
    db.commit()
    db.close()
    st = Store(path)
    assert st.roles()[0].slots == []
