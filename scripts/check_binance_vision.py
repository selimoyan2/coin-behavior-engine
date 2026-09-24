import httpx
import xml.etree.ElementTree as ET

client = httpx.Client(timeout=15.0)

s3_base = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"

prefixes = [
    "data/futures/um/monthly/klines/BTCUSDT/5m/",
    "data/futures/um/monthly/fundingRate/BTCUSDT/",
    "data/futures/um/monthly/metrics/BTCUSDT/",
    "data/futures/um/daily/metrics/BTCUSDT/",
]

for p in prefixes:
    url = f"{s3_base}?prefix={p}&max-keys=10"
    r = client.get(url)
    print(f"Prefix: {p} -> Status: {r.status_code}")
    if r.status_code == 200:
        root = ET.fromstring(r.text)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        contents = root.findall("s3:Contents", ns) or root.findall("Contents")
        print(f"  Contents count: {len(contents)}")
        for c in contents[:5]:
            key = c.find("s3:Key", ns) if c.find("s3:Key", ns) is not None else c.find("Key")
            size = c.find("s3:Size", ns) if c.find("s3:Size", ns) is not None else c.find("Size")
            if key is not None:
                print(f"    Key: {key.text} (Size: {size.text if size is not None else '?'})")
