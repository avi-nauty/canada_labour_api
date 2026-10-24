# Canada Tech Pulse API: Phase 1 notes (what I found out about Statistics Canada's API)

Date: October 23, 2026

## What the project is

Canada Tech Pulse API is a small FastAPI service I'm building that sits in front of Statistics Canada's Web Data Service (WDS). A caller asks a plain question ("unemployment rate, Ontario, ages 15-24, last 12 months") and my service translates it into the call StatCan understands, cleans up the reply, handles failures, and caches the result.

It is a portfolio project that practises resilient API design. It is not a product with users, and the data is monthly, so it is not real-time. Similar libraries already exist (`stats-can`, `cansim`, `statcanR`), so the point is not novelty, it's building the same idea carefully and being able to explain every decision.

Status: only Phase 1 (looking at the real data) is done. Phases 2 to 5 (client with retries, my own API, caching, deployment) are planned, not built.

## What Phase 1 was for

Before designing anything, I wanted to see what StatCan really returns, including when things go wrong, so that my design is based on real responses and not on the documentation's examples. (The docs' examples contradict each other in places, for example `value` shown as a string in one and a number in another.)

## How StatCan identifies a series

StatCan's service doesn't understand "Ontario" or "15-24". It understands a **vector ID**, a plain number that names exactly one time series (for example one region, one measure, one age group). My API's job is to map a human request to the right vector ID, so callers never see these numbers.

A series is also described by a **coordinate**, which is a string like `1.7.1.1.1.1.0.0.0.0`. It has one number per dimension of the table, in the table's fixed order, padded with zeros up to ten slots. The same coordinate means something different in every table, so a series is really identified by **product ID + coordinate**, and the vector ID is StatCan's shortcut for that pair.

The table I'm using is product ID **14100287** (table 14-10-0287, "Labour force characteristics, monthly, seasonally adjusted and trend-cycle"). Its six dimensions, in order:

| Position | Dimension | Members I used |
|---|---|---|
| 1 | Geography | 1 = Canada, 7 = Ontario |
| 2 | Labour force characteristics | 7 = Unemployment rate |
| 3 | Gender | 1 = Total - Gender |
| 4 | Age group | 1 = 15 years and over, 2 = 15 to 24 years |
| 5 | Statistics | 1 = Estimate |
| 6 | Data type | 1 = Seasonally adjusted |
| 7-10 | unused | 0 |

Careful: Ontario is 7 in position 1 and unemployment rate is also 7 in position 2. They are different dimensions. Age group IDs are not in order (15 to 64 is 8, 55 to 64 is 9), so I read 15-24 = 2 from the metadata, not guessed.

## The four series (what will go in `series.py`)

| Vector ID | Series | Coordinate |
|---|---|---|
| 2062815 | Canada, unemployment rate, 15+ | `1.7.1.1.1.1.0.0.0.0` |
| 2063949 | Ontario, unemployment rate, 15+ | `7.7.1.1.1.1.0.0.0.0` |
| 2062842 | Canada, unemployment rate, 15-24 | `1.7.1.2.1.1.0.0.0.0` |
| 2063976 | Ontario, unemployment rate, 15-24 | `7.7.1.2.1.1.0.0.0.0` |

Store vector IDs as plain integers. The request body wants `2063949`, not "V2063949".

## How I found the IDs

1. The StatCan website didn't show vector IDs where I expected, so I used the API instead.
2. I called `getCubeMetadata` for product 14100287. The reply lists every dimension with the ID of each member. From it I read Ontario = 7 and "15 to 24 years" = 2. I saved the reply as `cube_metadata.json` (it's large and can be regenerated, so it does not go in the repo).
3. I took Canada's known coordinate and changed only position 1 (Ontario) and position 4 (15-24) to build three new coordinates.
4. I called `getSeriesInfoFromCubePidCoord` with product ID + coordinate. It returns the vector ID and a series title.

## How I checked the IDs were right

- **Control:** the known Canada 15+ coordinate came back as vector 2062815, which I'd already confirmed. That proves the method and the coordinate format work.
- **Title check:** StatCan's returned title for each new vector says exactly what I intended (for example "Ontario;Unemployment rate;Total - Gender;15 to 24 years;Estimate;Seasonally adjusted"). The title is StatCan describing the dimensions of that vector.
- **Plausibility check:** I fetched the latest 12 months for all four. All came back `SUCCESS` with 12 points and the vector IDs I asked for. Ontario 15+ was within about a point of Canada 15+, and both youth series were far above their 15+ counterparts, with Ontario youth above Canada youth. A wrong dimension would still return clean-looking numbers, which is why the title check and the plausibility check are both needed.

I'm not recording the actual values here because they change every month and get revised.

## The call that returns data

`getDataFromVectorsAndLatestNPeriods`: POST to `https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods` with a JSON body that is a list of `{"vectorId": <int>, "latestN": <int>}`. StatCan uses POST for a read because the body is structured and can be long. My own endpoint will use GET since its inputs are three simple values.

Shape of one data point (real example):

```json
{"refPer":"2026-09-01","refPer2":"","refPerRaw":"2026-09-01","refPerRaw2":"","value":6.5,"decimals":1,"scalarFactorCode":0,"symbolCode":0,"statusCode":0,"securityLevelCode":0,"releaseTime":"2026-10-09T08:30","frequencyCode":6}
```

What matters:

- `refPer`: the first day of the month the value describes.
- `value`: a real number (nullable in my models, because `symbolCode` and `statusCode` are likely where suppression and quality flags show up, and all were 0 in what I saw).
- `decimals`: the precision of the value.
- `releaseTime`: when the value was **last revised**, not first published. After the October release, six past months all showed the same release time, so StatCan revises recent months. Consequence: refresh the whole window at each release, and don't use `releaseTime` in cache logic.
- The newest data point is last in the list.

## How it fails (all tested on purpose)

| What I sent | What came back | Lesson |
|---|---|---|
| Unknown but valid-sized ID (`999999999`) | HTTP **200**, but `"status":"FAILED"` and an empty `vectorDataPoint` | A client that only checks the HTTP status would treat this as valid empty data. Check each record's `status`. Never cache FAILED or empty. |
| 10-digit ID (`9999999999`) | HTTP **406** with a body that is not a list: `{"message":"JSON syntax error..."}` | Naive `data[0]` crashes. The message is misleading (my JSON was valid). A 4xx means my request is wrong, so don't retry. |
| Just over the 32-bit limit (`2147483648`) | HTTP 200, FAILED, but the echoed `vectorId` was `2147483647` | StatCan silently changed my ID. The vector ID in the reply can't be trusted as an echo, so match each record to what I requested and treat a mismatch as an error. I don't know why this one is clamped while the 10-digit one gives a 406, and I'm not chasing it, since IDs will only come from `series.py`. |

I saved the three responses as sample files. In Phase 2 they become the fake StatCan used in offline tests, with the HTTP status (200, 200, 406) kept alongside each one.

## What StatCan's documentation says (read, not tested by me)

- Rate limits: 50 requests per second server-wide, 25 per second per IP.
- The service runs 24/7, data updates every business day at 8:30 am Eastern, and from midnight until 8:30 am some methods may not return data. Locked tables can give HTTP 409. So 409 is possible, not guaranteed, and during that window a method may return an empty list that looks like "no data". Use `America/Toronto` in code, not a fixed offset.
- The Labour Force Survey releases at 8:30 am Eastern: Nov 6, 2026 (October data), Dec 4, 2026 (November), Jan 8, 2027 (December). The latest month available now is September 2026. This drives the cache lifetime.

## Planned order of checks in my client (Phase 2)

1. HTTP status first. 4xx means my request is wrong, so don't retry. 5xx, 429 and timeouts get retried with back-off and jitter. 409 maps to my own 503 with a `Retry-After`.
2. Only after a 200: parse as a list, check each record's `status`, and confirm the `vectorId` matches the request. FAILED raises an error, which maps to my own 502.
3. Never cache an empty, FAILED or 409 response.

## An unsolved problem

Sometimes the connection hangs for 60 seconds and fails with `httpx.ConnectTimeout` raised during the TLS handshake. It happened on my first run and again on one request in the lookup script. Curl to the same URL worked, so the network and StatCan were fine.

What I did: built an SSL context from `certifi` and capped TLS at version 1.2. It worked, but I changed two things at once, so I don't know which one mattered, and the timeout still happened once with both in place. **Cause not identified. The failure is intermittent.** I won't claim a cause in the README. It does show why the client must retry timeouts. Untried: `httpx.get("https://example.com")`, a phone hotspot, turning off any VPN.

## What's done and what's not

Done and checked:
- A real call to the StatCan API works from Python.
- Four vector IDs confirmed by title, control and plausibility check.
- Real field names and value types observed.
- Three failure shapes observed and sample responses saved.

Not done:
- Phase 2 onward: the client, tests, my own API, caching, Docker, deploy, README. None of it is built yet.
- The project folder (uv and git) isn't set up yet. It's planned for the start of Phase 2.
- The 300-vectors-per-request batch limit is unconfirmed (irrelevant while requesting a handful of series).
- The meaning of each `responseStatusCode` number is unconfirmed. Observed: 0 on success, 3 on an unknown ID. Branch on `status`, only log the code.

## How I'd explain this to someone

"Statistics Canada has a data API, but it identifies series by numeric vector IDs and fails in awkward ways: a failed lookup returns HTTP 200, some errors return a body that isn't even a list, and recent months get revised. I'm building a small FastAPI layer that takes a plain request like region and age group, handles those failure modes, and caches the monthly data. So far I've mapped four series by finding the right IDs through StatCan's own metadata, verified them, and recorded how the API behaves when things go wrong. Next I'm building the client with retries and offline tests, then my own API in front of it."

Say "I'm building" for anything not yet done, and "I built" only for what exists.