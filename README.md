# Canada Labour API

A small FastAPI service that I'm building in front of Statistics Canada's Web Data Service. The goal is to let a caller ask for labour data in plain terms (for example, Ontario unemployment for ages 15-24, last 12 months) without knowing StatCan's internal series IDs, and to handle the ways StatCan's API can fail.

**Status: work in progress.** This is a portfolio project, not a product. The data is published monthly, so nothing here is real-time.

## What works today

- A StatCan client (`app/services/statcan.py`) that fetches the latest N periods for a series by vector ID.
- A FastAPI app (`app/main.py`) with `GET /v1/unemployment` (region, age group, number of periods), `GET /v1/series` and `GET /v1/health`. Bad input returns 422, an unmapped region and age group combination returns 404, a locked table returns 503 with a `Retry-After` header, and any other StatCan failure returns 502. Interactive docs are served at `/docs` when it runs.
- Retries with exponential back-off and jitter (up to 4 attempts) for network failures, HTTP 5xx, 429 and 409 (locked table). Errors that waiting can't fix fail immediately instead.
- An in-memory cache (`app/services/cache.py`) that keeps the latest 120 points per series and slices them to the requested number of periods. An entry is trusted for up to 24 hours, but once a scheduled release has passed and the stored data is still a month behind, it is rechecked every 5 minutes. Failed calls are never cached. The cache is empty after a restart, and two simultaneous requests on an empty cache both call StatCan. The release dates are hardcoded in the module.
- Explicit error types, all subclasses of `StatCanError`:
  - `SeriesNotFoundError`: a `FAILED` record inside an HTTP 200 reply (seen on the live service).
  - `BadRequestError`: an HTTP 406 reply (seen on the live service).
  - `RetryableError` and `TableLockedError`: 429 or 5xx, and 409, raised once the retries run out.
  - `UnexpectedResponseError`: a reply that isn't the expected shape, or a success with no data points.
  - plain `StatCanError`: any other non-200 status.
- 43 offline tests (13 for the client, 19 for the API endpoints, 11 for the cache) that run against fake StatCan replies and a fake clock, with no network. The 409, 429 and 5xx cases are simulated, since I haven't seen the live service return them.
- Recorded StatCan replies in `tests/fixtures/` for offline testing.
- Notes on the table structure and the four series I've confirmed (`notes.md`).

## What I'm building next

1. Check how StatCan behaves on a release morning. The one time I called it inside the overnight window (a night with no release) it returned a normal reply, so I still don't know what the service does around a release. The client already treats HTTP 409 as retryable.
2. Check the cache on a real release morning, and extend the hardcoded release dates past January 2027.
3. Docker, CI and deployment.

## Data source

Adapted from Statistics Canada, Table 14-10-0287, *Labour force characteristics, monthly, seasonally adjusted and trend-cycle*, data through September 2026. This does not constitute an endorsement by Statistics Canada of this product.

## Try the client

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
uv run python -c "from app.services.statcan import fetch_latest; print(fetch_latest(2062815, 3))"
```

Vector 2062815 is the Canada-wide unemployment rate for ages 15 and over.

## Run the API

```
uv sync
uv run fastapi dev app/main.py
```

Then open http://127.0.0.1:8000/docs and try `/v1/unemployment`, or call it directly, for example `/v1/unemployment?region=ON&age_group=15-24&periods=12`. In a raw URL, `age_group=15+` works too, even though a browser sends `+` as a space; the API accepts that one case on purpose.