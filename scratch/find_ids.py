import json
import ssl
import certifi
import httpx

BASE = "https://www150.statcan.gc.ca/t1/wds/rest/"
ctx = ssl.create_default_context(cafile=certifi.where())
ctx.maximum_version = ssl.TLSVersion.TLSv1_2

response = httpx.post(
    BASE + "getCubeMetadata",
    json=[{"productId": 14100287}],
    timeout=60,
    verify=ctx,
)
print(response.status_code)
print(response.text)

with open("cube_metadata.json", "w") as f:
    json.dump(response.json(), f, indent=2)