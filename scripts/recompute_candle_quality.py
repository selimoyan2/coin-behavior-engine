import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Load November 2026 5m parquet
fpath = "data/binance_spot_multiyear/5m/BTCUSDT-5m-2026-11.parquet"
df = pd.read_parquet(fpath)
print(f"Loaded {len(df)} candles from {fpath}")

# Sort by open_time
df = df.sort_values("open_time").reset_index(drop=True)
df["dt"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
print(f"Start: {df['dt'].min()} UTC, End: {df['dt'].max()} UTC")

# Check expected 5m sequence
start_dt = df["dt"].min()
end_dt = df["dt"].max()
expected_range = pd.date_range(start_dt, end_dt, freq="5min", tz="UTC")
actual_set = set(df["dt"])
missing = [dt for dt in expected_range if dt not in actual_set]

print(f"\nTotal expected in span: {len(expected_range)}")
print(f"Total actual in span: {len(df)}")
print(f"Total missing in span: {len(missing)}")
print("Missing 5m timestamps:")
for m in missing:
    print(f"  - {m.strftime('%Y-%m-%d %H:%M:%S UTC')} (epoch ms: {int(m.timestamp()*1000)})")

# Analyze higher timeframes
timeframes = {
    "15m": {"freq": "15min", "sub_per_bar": 3, "file": "data/binance_spot_multiyear/15m/BTCUSDT-15m-2026-11.parquet"},
    "1h": {"freq": "1h", "sub_per_bar": 12, "file": "data/binance_spot_multiyear/1h/BTCUSDT-1h-2026-11.parquet"},
    "4h": {"freq": "4h", "sub_per_bar": 48, "file": "data/binance_spot_multiyear/4h/BTCUSDT-4h-2026-11.parquet"},
    "1d": {"freq": "1D", "sub_per_bar": 288, "file": "data/binance_spot_multiyear/1d/BTCUSDT-1d-2026-11.parquet"},
}

for tf, cfg in timeframes.items():
    print(f"\n=================== TIMEFRAME: {tf} ===================")
    tf_df = pd.read_parquet(cfg["file"])
    tf_df["dt"] = pd.to_datetime(tf_df["open_time"], unit="ms", utc=True)
    print(f"Total rows in {tf} parquet: {len(tf_df)}")
    print(f"Start: {tf_df['dt'].min()} UTC, End: {tf_df['dt'].max()} UTC")

    # Floor each missing 5m candle to the tf bucket
    affected_buckets = {}
    for m in missing:
        bucket = m.floor(cfg["freq"])
        affected_buckets.setdefault(bucket, []).append(m)
    
    print(f"Total {tf} candles affected by gaps (GAP_AFFECTED): {len(affected_buckets)}")
    for b_dt, m_list in sorted(affected_buckets.items()):
        sub_in_file = len(df[df["dt"].apply(lambda x: x.floor(cfg["freq"])) == b_dt])
        print(f"  Bar Open: {b_dt.strftime('%Y-%m-%d %H:%M:%S UTC')} | Missing sub-bars: {len(m_list)}/{cfg['sub_per_bar']} (Present in 5m: {sub_in_file})")
        for m in m_list:
            print(f"     -> missing 5m: {m.strftime('%H:%M')}")
            
    # Check incomplete candle (final candle of the partial month)
    final_bar_dt = tf_df["dt"].max()
    final_sub_candles = [dt for dt in actual_set if dt.floor(cfg["freq"]) == final_bar_dt]
    bar_end = final_bar_dt + pd.Timedelta(cfg["freq"])
    expected_subs_in_bar = len(pd.date_range(final_bar_dt, bar_end - pd.Timedelta("5min"), freq="5min", tz="UTC"))
    is_incomplete = len(final_sub_candles) < expected_subs_in_bar
    print(f"\n  Final Bar Open: {final_bar_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Sub-bars present: {len(final_sub_candles)}/{expected_subs_in_bar}")
    print(f"  Classification: {'INCOMPLETE_CANDLE' if is_incomplete else 'COMPLETE_VERIFIED'}")
