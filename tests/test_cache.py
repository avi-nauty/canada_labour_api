from datetime import date, datetime, timezone

import pytest

from app.services.cache import InMemoryCache, expected_month, get_points
from app.services.statcan import RetryableError

VECTOR = 2063949


def utc(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def points(ref_per):
    return [{"refPer": ref_per, "value": 7.0}]


def fake_statcan(monkeypatch, results):
    calls = []

    def fake(vector_id, periods):
        calls.append((vector_id, periods))
        result = results[len(calls) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("app.services.cache.fetch_latest", fake)
    return calls


@pytest.fixture
def cache():
    return InMemoryCache()


def test_miss_then_hit(monkeypatch, cache):
    calls = fake_statcan(monkeypatch, [points("2026-09-01")])
    first, fetched_at, cached = get_points(VECTOR, now=utc(2026, 11, 3, 15), cache=cache)
    assert cached is False
    assert calls == [(VECTOR, 120)]
    second, fetched_at2, cached2 = get_points(VECTOR, now=utc(2026, 11, 3, 16), cache=cache)
    assert cached2 is True
    assert second == first
    assert fetched_at2 == utc(2026, 11, 3, 15)
    assert len(calls) == 1


def test_entry_expires_after_24_hours(monkeypatch, cache):
    calls = fake_statcan(monkeypatch, [points("2026-09-01"), points("2026-09-01")])
    get_points(VECTOR, now=utc(2026, 11, 3, 15), cache=cache)
    _, _, cached = get_points(VECTOR, now=utc(2026, 11, 4, 16), cache=cache)
    assert cached is False
    assert len(calls) == 2


def test_release_makes_old_entry_stale_even_inside_24_hours(monkeypatch, cache):
    calls = fake_statcan(monkeypatch, [points("2026-09-01"), points("2026-10-01")])
    get_points(VECTOR, now=utc(2026, 11, 5, 15), cache=cache)
    result, _, cached = get_points(VECTOR, now=utc(2026, 11, 6, 13, 31), cache=cache)
    assert cached is False
    assert result[-1]["refPer"] == "2026-10-01"
    assert len(calls) == 2


def test_behind_entry_is_rechecked_every_five_minutes(monkeypatch, cache):
    calls = fake_statcan(monkeypatch, [points("2026-09-01"), points("2026-10-01")])
    _, _, cached = get_points(VECTOR, now=utc(2026, 11, 6, 13, 31), cache=cache)
    assert cached is False
    result, _, cached = get_points(VECTOR, now=utc(2026, 11, 6, 13, 33), cache=cache)
    assert cached is True
    assert result[-1]["refPer"] == "2026-09-01"
    result, _, cached = get_points(VECTOR, now=utc(2026, 11, 6, 13, 37), cache=cache)
    assert cached is False
    assert result[-1]["refPer"] == "2026-10-01"
    assert len(calls) == 2


def test_current_entry_after_release_is_kept(monkeypatch, cache):
    calls = fake_statcan(monkeypatch, [points("2026-10-01")])
    get_points(VECTOR, now=utc(2026, 11, 6, 13, 31), cache=cache)
    _, _, cached = get_points(VECTOR, now=utc(2026, 11, 6, 14, 31), cache=cache)
    assert cached is True
    assert len(calls) == 1


def test_errors_are_not_stored(monkeypatch, cache):
    calls = fake_statcan(monkeypatch, [RetryableError("503"), points("2026-09-01")])
    with pytest.raises(RetryableError):
        get_points(VECTOR, now=utc(2026, 11, 3, 15), cache=cache)
    assert cache.get(VECTOR) is None
    _, _, cached = get_points(VECTOR, now=utc(2026, 11, 3, 15, 1), cache=cache)
    assert cached is False
    assert len(calls) == 2


@pytest.mark.parametrize(
    "now, expected",
    [
        (utc(2026, 11, 3, 15), None),
        (utc(2026, 11, 6, 13, 29), None),
        (utc(2026, 11, 6, 13, 31), date(2026, 10, 1)),
        (utc(2026, 12, 4, 13, 31), date(2026, 11, 1)),
        (utc(2027, 1, 8, 13, 31), date(2026, 12, 1)),
    ],
)
def test_expected_month(now, expected):
    assert expected_month(now) == expected