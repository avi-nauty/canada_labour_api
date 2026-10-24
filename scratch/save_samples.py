import json
import ssl
from pathlib import Path

import certifi
import httpx

URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"
OUT = Path("tests/fixtures")
OUT.mkdir(parents=True, exist_ok=True)

ctx = ssl.create_default_context(cafile=certifi.where())
ctx.maximum_version = ssl.TLSVersion.TLSv1_2

cases = {
    "sample_success.json": (2062815, 12),
    "sample_failed.json": (999999999, 3),
    "sample_406.json": (9999999999, 3),
}

with httpx.Client(verify=ctx, timeout=60) as client:
    for filename, (vector_id, n) in cases.items():
        r = client.post(URL, json=[{"vectorId": vector_id, "latestN": n}])
        print(filename, r.status_code)
        with open(OUT / filename, "w") as f:
            json.dump({"status_code": r.status_code, "body": r.json()}, f, indent=2)