# Canada Labour API

A small FastAPI service that I'm building in front of Statistics Canada's Web Data Service. The goal is to let a caller ask for labour data in plain terms (for example, Ontario unemployment for ages 15-24, last 12 months) without knowing StatCan's internal series IDs, and to handle the ways StatCan's API can fail.

**Status: work in progress.** This is a portfolio project, not a product. The data is published monthly, so nothing here is real-time.

## What works today

- A StatCan client (`app/services/statcan.py`) that fetches the latest N periods for a series by vector ID.
- Retries with exponential back-off and jitter (up to 4 attempts) for network failures, HTTP 5xx, 429 and 409 (locked table). Errors that waiting can't fix fail immediately instead.
- Explicit error types, all subclasses of `StatCanError`:
  - `SeriesNotFoundError`: a `FAILED` record inside an HTTP 200 reply (seen on the live service).
  - `BadRequestError`: an HTTP 406 reply (seen on the live service).
  - `RetryableError` and `TableLockedError`: 429 or 5xx, and 409, raised once the retries run out.
  - `UnexpectedResponseError`: a reply that isn't the expected shape, or a success with no data points.
  - plain `StatCanError`: any other non-200 status.
- 11 offline tests that run against fake StatCan replies, with no network. The 409, 429 and 5xx cases are simulated, since I haven't seen the live service return them.
- Recorded StatCan replies in `tests/fixtures/` for offline testing.
- Notes on the table structure and the four series I've confirmed (`notes.md`).

## What I'm building next

1. Find out how StatCan behaves during its overnight update window (midnight to 8:30 am Eastern). The client already treats HTTP 409 as retryable, but I haven't observed what the service actually returns then.
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