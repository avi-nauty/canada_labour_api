import ssl
import certifi
import httpx

BASE = "https://www150.statcan.gc.ca/t1/wds/rest/"
ctx = ssl.create_default_context(cafile=certifi.where())
ctx.maximum_version = ssl.TLSVersion.TLSv1_2

coords = {
    "Canada 15+ (known)": "1.7.1.1.1.1.0.0.0.0",
    "Ontario 15+":        "7.7.1.1.1.1.0.0.0.0",
    "Canada 15-24":       "1.7.1.2.1.1.0.0.0.0",
    "Ontario 15-24":      "7.7.1.2.1.1.0.0.0.0",
}

with httpx.Client(verify=ctx, timeout=60) as client:
    for name, coord in coords.items():
        r = client.post(
            BASE + "getSeriesInfoFromCubePidCoord",
            json=[{"productId": 14100287, "coordinate": coord}],
        )
        print("---", name, r.status_code)
        print(r.text)
        print()
        