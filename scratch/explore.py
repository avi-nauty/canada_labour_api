import ssl
import certifi
import httpx

URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"

ctx = ssl.create_default_context(cafile=certifi.where())
ctx.maximum_version = ssl.TLSVersion.TLSv1_2

cases = {
    "success (real vector)": 2062815,
    "FAILED (unknown id)": 999999999,
    "406 (10-digit id)": 9999999999,
    "clamped (just over 32-bit)": 2147483648,
}

for name, vector_id in cases.items():
    response = httpx.post(
        URL,
        json=[{"vectorId": vector_id, "latestN": 3}],
        timeout=60,
        verify=ctx,
    )
    print(f"--- {name} ---")
    print(response.status_code)
    print(response.text)
    print()