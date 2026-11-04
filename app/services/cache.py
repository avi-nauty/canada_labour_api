from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from app.services.statcan import fetch_latest

TORONTO = ZoneInfo("America/Toronto")
WINDOW = 120
MAX_AGE = timedelta(hours=24)
BEHIND_RECHECK = timedelta(minutes=5)

RELEASES = [
    datetime(2026, 11, 6, 8, 30, tzinfo=TORONTO),
    datetime(2026, 12, 4, 8, 30, tzinfo=TORONTO),
    datetime(2027, 1, 8, 8, 30, tzinfo=TORONTO),
]


@dataclass
class Entry:
    points: list[dict]
    fetched_at: datetime


class Cache(Protocol):
    def get(self, key: int) -> Entry | None: ...
    def set(self, key: int, entry: Entry) -> None: ...


class InMemoryCache:
    def __init__(self):
        self._data: dict[int, Entry] = {}

    def get(self, key: int) -> Entry | None:
        return self._data.get(key)

    def set(self, key: int, entry: Entry) -> None:
        self._data[key] = entry


_cache = InMemoryCache()


def expected_month(now: datetime) -> date | None:
    released = [r for r in RELEASES if r <= now]
    if not released:
        return None
    latest = released[-1]
    year, month = latest.year, latest.month - 1
    if month == 0:
        year, month = year - 1, 12
    return date(year, month, 1)


def is_fresh(entry: Entry, now: datetime) -> bool:
    newest = date.fromisoformat(entry.points[-1]["refPer"])
    expected = expected_month(now)
    behind = expected is not None and newest < expected
    limit = BEHIND_RECHECK if behind else MAX_AGE
    return now - entry.fetched_at < limit


def get_points(
    vector_id: int,
    now: datetime | None = None,
    cache: Cache | None = None,
) -> tuple[list[dict], datetime, bool]:
    if now is None:
        now = datetime.now(timezone.utc)
    if cache is None:
        cache = _cache
    entry = cache.get(vector_id)
    if entry is not None and is_fresh(entry, now):
        return entry.points, entry.fetched_at, True
    points = fetch_latest(vector_id, WINDOW)
    cache.set(vector_id, Entry(points=points, fetched_at=now))
    return points, now, False