import httpx
import zipfile
import io
import pandas as pd

url = "https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2021-01.zip"
r = httpx.get(url, timeout=15.0)
print(f"Status for 2021-01 perp klines: {r.status_code}")
if r.status_code == 200:
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    print("Files in zip:", zf.namelist())
    for name in zf.namelist():
        with zf.open(name) as f:
            df = pd.read_csv(f, header=None)
            print(f"\n--- {name} ---")
            print("Shape:", df.shape)
            print("Head 2:")
            print(df.head(2))
