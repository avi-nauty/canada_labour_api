import json
from pathlib import Path

import httpx

from app.services.statcan import fetch_latest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with open(FIXTURES / name) as f:
        return json.load(f)


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_success_returns_data_points():
    fixture = load_fixture("sample_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(fixture["status_code"], json=fixture["body"])

    result = fetch_latest(2062815, 12, client=make_client(handler))

    assert len(result) == 12
    assert result[-1]["refPer"] == "2026-09-01"
    assert result[-1]["value"] == 6.5