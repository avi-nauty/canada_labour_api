import json
from pathlib import Path
import httpx
import pytest
from tenacity import wait_none

from app.services.statcan import BadRequestError, SeriesNotFoundError, fetch_latest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))

@pytest.fixture(autouse=True)
def no_retry_wait(monkeypatch):
    monkeypatch.setattr(fetch_latest.retry, "wait", wait_none())

def sequence_handler(responses: list, calls: list):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        status, body = responses[len(calls) - 1]
        return httpx.Response(status, json=body)

    return handler

def fixture_handler(fixture: dict, calls: list):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(fixture["status_code"], json=fixture["body"])

    return handler

def test_success_returns_data_points():
    fixture = load_fixture("sample_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(fixture["status_code"], json=fixture["body"])

    result = fetch_latest(2062815, 12, client=make_client(handler))

    assert len(result) == 12
    assert result[-1]["refPer"] == "2026-09-01"
    assert result[-1]["value"] == 6.5

def test_failed_record_raises_and_is_not_retried():
    fixture = load_fixture("sample_failed.json")
    calls = []
    client = make_client(fixture_handler(fixture, calls))

    with pytest.raises(SeriesNotFoundError):
        fetch_latest(999999999, 3, client=client)

    assert len(calls) == 1


def test_bad_request_raises_and_is_not_retried():
    fixture = load_fixture("sample_406.json")
    calls = []
    client = make_client(fixture_handler(fixture, calls))

    with pytest.raises(BadRequestError):
        fetch_latest(9999999999, 3, client=client)

    assert len(calls) == 1

def test_retries_503_then_succeeds():
    success = load_fixture("sample_success.json")
    responses = [(503, {}), (503, {}), (success["status_code"], success["body"])]
    calls = []
    client = make_client(sequence_handler(responses, calls))

    result = fetch_latest(2062815, 12, client=client)

    assert len(result) == 12
    assert len(calls) == 3