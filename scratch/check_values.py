import ssl
import certifi
import httpx

URL = "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods"

ctx = ssl.create_default_context(cafile=certifi.where())
#ctx.maximum_version = ssl.TLSVersion.TLSv1_2

names = {
    2062815: "Canada 15+ (control)",
    2063949: "Ontario 15+",
    2062842: "Canada 15-24",
    2063976: "Ontario 15-24",
}

body = [{"vectorId": vid, "latestN": 12} for vid in names]

response = httpx.post(URL, json=body, timeout=60, verify=ctx)
print(response.status_code)

for record in response.json():
    obj = record["object"]
    points = obj["vectorDataPoint"]
    last = points[-1]
    print(
        names.get(obj["vectorId"], "UNEXPECTED ID"),
        record["status"],
        obj["vectorId"],
        len(points),
        last["refPer"],
        last["value"],
    )