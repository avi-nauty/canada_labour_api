import ssl
import certifi
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential


class StatCanError(Exception):
    pass

class BadRequestError(StatCanError):
    pass

class SeriesNotFoundError(StatCanError):
    pass

class RetryableError(StatCanError):
    pass

class TableLockedError(StatCanError):
    pass

URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"

_ctx = ssl.create_default_context(cafile=certifi.where())
_ctx.maximum_version = ssl.TLSVersion.TLSv1_2

_client = httpx.Client(verify=_ctx, timeout=httpx.Timeout(30, connect=5))

@retry(
    retry=retry_if_exception_type((RetryableError, TableLockedError, httpx.TransportError)),
    stop=stop_after_attempt(4),
    wait=wait_random_exponential(multiplier=1, max=10),
    reraise=True)

def fetch_latest(vector_id: int, periods: int) -> list[dict]:
    body = [{"vectorId": vector_id, "latestN": periods}]
    response = _client.post(URL, json=body)
    if response.status_code == 406:
        raise BadRequestError(f"StatCan rejected the request: {response.text}")
    if response.status_code == 409:
        raise TableLockedError(f"StatCan table is locked (HTTP 409): {response.text}")
    if response.status_code == 429:
        raise RetryableError(f"StatCan rate limit hit (HTTP 429): {response.text}")
    if response.status_code >= 500:
        raise RetryableError(f"StatCan server error (HTTP {response.status_code}): {response.text}")
    if response.status_code != 200:
        raise StatCanError(f"Unexpected HTTP status {response.status_code}: {response.text}")
    record = response.json()[0]
    if record["status"] != "SUCCESS":
        code = record["object"]["responseStatusCode"]
        raise SeriesNotFoundError(
            f"Vector {vector_id} not found (responseStatusCode {code})"
        )

    return record["object"]["vectorDataPoint"]