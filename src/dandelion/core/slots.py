# SPDX-License-Identifier: GPL-3.0-or-later
"""Feste Zeitslots pro Rolle („jeden Montag 08:00“) und der nächste freie Slot."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, tzinfo

WEEKDAYS = 7


def slot_times(slots: Iterable[list[object]], start: datetime, days: int = 28) -> list[datetime]:
    """Alle Slot-Termine ab `start` (aware) für die nächsten `days` Tage, sortiert."""
    tz: tzinfo | None = start.tzinfo
    out: list[datetime] = []
    base = start.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(days + 1):
        day = base + timedelta(days=offset)
        for weekday, hm in slots:
            if int(weekday) != day.weekday():   # type: ignore[call-overload]
                continue
            try:
                hour, minute = (int(x) for x in str(hm).split(":"))
            except ValueError:
                continue
            when = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            if when > start:
                out.append(when)
    return sorted(set(out))


def next_free_slot(slots: Iterable[list[object]], taken: Iterable[datetime], now: datetime,
                   min_lead: timedelta = timedelta(minutes=2)) -> datetime | None:
    """Nächster Slot, der nicht schon von einem geplanten Beitrag belegt ist."""
    busy = list(taken)
    for when in slot_times(list(slots), now + min_lead):
        if not any(abs((when - t).total_seconds()) < 60 for t in busy):
            return when
    return None
