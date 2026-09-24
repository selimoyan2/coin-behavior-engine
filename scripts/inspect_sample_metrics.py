import httpx
import zipfile
import io
import pandas as pd

url = "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2021-01-01.zip"
r = httpx.get(url, timeout=15.0)
print(f"Status for 2021-01-01 metrics: {r.status_code}")
if r.status_code == 200:
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    print("Files in zip:", zf.namelist())
    for name in zf.namelist():
        with zf.open(name) as f:
            df = pd.read_csv(f)
            print(f"\n--- {name} ---")
            print("Shape:", df.shape)
            print("Columns:", list(df.columns))
            print("Head 3:")
            print(df.head(3))
