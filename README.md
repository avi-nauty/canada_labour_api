# Canada Labour API

A small FastAPI service I'm building in front of Statistics Canada's Web Data Service. The goal is to let a caller ask for labour data in plain terms (for example, Ontario unemployment for ages 15-24, last 12 months) without knowing StatCan's internal series IDs, and to handle the ways StatCan's API can fail.

**Status: work in progress.** This is a portfolio project, not a product. The data is published monthly, so nothing here is real-time.

## What works today

- A StatCan client (`app/services/statcan.py`) that fetches the latest N periods for a series by vector ID.
- Explicit errors for the two failure modes I found by testing the live service:
  - A `FAILED` record inside an HTTP 200 reply (unknown series) raises `SeriesNotFoundError`.
  - An HTTP 406 reply, whose body is not a list, raises `BadRequestError`.
- Recorded StatCan replies in `tests/fixtures/` for offline testing.
- Notes on the table structure and the four series I've confirmed (`notes.md`).

## What I'm building next

1. Retries with exponential back-off and jitter for timeouts, 5xx and 429, and explicit handling of StatCan's overnight update window.
2. Tests for the client using mocked StatCan responses.
3. The API itself: `GET /v1/unemployment` with region, age group and number of periods, plus `/v1/series` and `/v1/health`.
4. A cache that expires when StatCan publishes its next monthly release.
5. Docker, CI and deployment.

## Data source

Statistics Canada, Table 14-10-0287, *Labour force characteristics, monthly, seasonally adjusted and trend-cycle*. Contains information licensed under the Statistics Canada Open Licence.

## Try the client

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
uv run python -c "from app.services.statcan import fetch_latest; print(fetch_latest(2062815, 3))"
```

Vector 2062815 is the Canada-wide unemployment rate for ages 15 and over.