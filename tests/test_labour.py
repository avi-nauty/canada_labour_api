import json
from pathlib import Path
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.series import SeriesNotMappedError
from app.services.statcan import (
    BadRequestError,
    RetryableError,
    SeriesNotFoundError,
    StatCanError,
    TableLockedError,
    UnexpectedResponseError,
)

FIXTURES = Path(__file__).parent / "fixtures"

client = TestClient(app)


def sample_points() -> list[dict]:
    with open(FIXTURES / "sample_success.json") as f:
        return json.load(f)["body"][0]["object"]["vectorDataPoint"]


def fake_fetch(monkeypatch, result=None, error=None) -> list:
    calls = []

    def fake(vector_id):
        calls.append(vector_id)
        if error is not None:
            raise error
        return result, datetime(2026, 11, 3, 22, 46, tzinfo=timezone.utc), False

    monkeypatch.setattr("app.routers.labour.get_points", fake)
    return calls


def test_health():
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_series_lists_all_four_mappings():
    response = client.get("/v1/series")
    assert response.status_code == 200
    assert len(response.json()) == 4


def test_unemployment_success(monkeypatch):
    calls = fake_fetch(monkeypatch, result=sample_points())
    response = client.get(
        "/v1/unemployment", params={"region": "CA", "age_group": "15+", "periods": 12}
    )
    assert response.status_code == 200
    body = response.json()
    assert calls == [2062815]
    assert body["metadata"]["vector_id"] == 2062815
    assert body["metadata"]["region"] == "CA"
    assert body["metadata"]["age_group"] == "15+"
    assert body["metadata"]["cached"] is False
    assert len(body["data"]) == 12
    assert body["data"][-1] == {"ref_period": "2026-09-01", "value": 6.5}


def test_unemployment_keeps_null_values(monkeypatch):
    fake_fetch(monkeypatch, result=[{"refPer": "2026-09-01", "value": None}])
    response = client.get(
        "/v1/unemployment", params={"region": "ON", "age_group": "15-24", "periods": 1}
    )
    assert response.status_code == 200
    assert response.json()["data"] == [{"ref_period": "2026-09-01", "value": None}]


@pytest.mark.parametrize(
    "params",
    [
        {"region": "XX", "age_group": "15+"},
        {"region": "ON", "age_group": "nope"},
        {"region": "ON", "age_group": "15+", "periods": 0},
        {"region": "ON", "age_group": "15+", "periods": 121},
        {"region": "ON", "age_group": "15+", "periods": "abc"},
        {"region": "ON"},
    ],
)
def test_bad_input_returns_422_and_never_calls_statcan(monkeypatch, params):
    calls = fake_fetch(monkeypatch, result=sample_points())
    response = client.get("/v1/unemployment", params=params)
    assert response.status_code == 422
    assert calls == []


def test_unmapped_combination_returns_404(monkeypatch):
    def fake_get_series(region, age_group):
        raise SeriesNotMappedError("No series for region ON and age group 15+")

    monkeypatch.setattr("app.routers.labour.get_series", fake_get_series)
    response = client.get(
        "/v1/unemployment", params={"region": "ON", "age_group": "15+"}
    )
    assert response.status_code == 404
    assert "No series" in response.json()["detail"]


def test_locked_table_returns_503_with_retry_after(monkeypatch):
    fake_fetch(monkeypatch, error=TableLockedError("locked"))
    response = client.get(
        "/v1/unemployment", params={"region": "ON", "age_group": "15+"}
    )
    assert response.status_code == 503
    assert response.headers["retry-after"] == "300"


@pytest.mark.parametrize(
    "error",
    [
        RetryableError("503"),
        SeriesNotFoundError("missing"),
        BadRequestError("bad"),
        UnexpectedResponseError("odd"),
        StatCanError("other"),
        httpx.ConnectTimeout("timed out"),
    ],
)
def test_other_failures_return_502(monkeypatch, error):
    fake_fetch(monkeypatch, error=error)
    response = client.get(
        "/v1/unemployment", params={"region": "ON", "age_group": "15+"}
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Data source failed"

def test_unencoded_plus_in_age_group_is_accepted(monkeypatch):
    calls = fake_fetch(monkeypatch, result=sample_points())
    response = client.get("/v1/unemployment?region=CA&age_group=15+&periods=12")
    assert response.status_code == 200
    assert calls == [2062815]
    assert response.json()["metadata"]["age_group"] == "15+"