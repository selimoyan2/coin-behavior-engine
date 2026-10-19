import pandas as pd
import numpy as np
from pathlib import Path

def diagnose():
    raw_path = Path("data/raw/btcusdt_5m_raw.parquet")
    df_raw = pd.read_parquet(raw_path)
    df_raw["open_time"] = df_raw["timestamp_open"].astype("int64")
    print(f"Total raw rows: {len(df_raw)}")

    vision_5m_dir = Path("data/binance_spot_multiyear/5m")
    
    total_compared = 0
    mismatched_candles = []
    
    for f in sorted(vision_5m_dir.glob("BTCUSDT-5m-*.parquet")):
        df_v = pd.read_parquet(f)
        df_merged = pd.merge(df_raw, df_v, on="open_time", suffixes=("_raw", "_vis"))
        if len(df_merged) == 0:
            continue
            
        total_compared += len(df_merged)
        
        diff_close = np.abs(df_merged["close_raw"].astype(float) - df_merged["close_vis"].astype(float))
        diff_high = np.abs(df_merged["high_raw"].astype(float) - df_merged["high_vis"].astype(float))
        diff_low = np.abs(df_merged["low_raw"].astype(float) - df_merged["low_vis"].astype(float))
        diff_open = np.abs(df_merged["open_raw"].astype(float) - df_merged["open_vis"].astype(float))
        diff_vol = np.abs(df_merged["base_volume"].astype(float) - df_merged["volume"].astype(float))
        
        # Check tolerance > 0.01 USDT or volume > 0.01 BTC
        mask_diff = (diff_close > 0.01) | (diff_high > 0.01) | (diff_low > 0.01) | (diff_open > 0.01) | (diff_vol > 0.01)
        
        if mask_diff.any():
            diff_rows = df_merged[mask_diff]
            for idx, r in diff_rows.iterrows():
                ts_utc = str(pd.to_datetime(r["open_time"], unit="ms", utc=True))
                mismatched_candles.append({
                    "open_time": int(r["open_time"]),
                    "datetime_utc": ts_utc,
                    "month": f.stem,
                    "raw_open": float(r["open_raw"]),
                    "vis_open": float(r["open_vis"]),
                    "raw_high": float(r["high_raw"]),
                    "vis_high": float(r["high_vis"]),
                    "raw_low": float(r["low_raw"]),
                    "vis_low": float(r["low_vis"]),
                    "raw_close": float(r["close_raw"]),
                    "vis_close": float(r["close_vis"]),
                    "raw_volume": float(r["base_volume"]),
                    "vis_volume": float(r["volume"]),
                    "diff_open": float(abs(float(r["open_raw"]) - float(r["open_vis"]))),
                    "diff_high": float(abs(float(r["high_raw"]) - float(r["high_vis"]))),
                    "diff_low": float(abs(float(r["low_raw"]) - float(r["low_vis"]))),
                    "diff_close": float(abs(float(r["close_raw"]) - float(r["close_vis"]))),
                    "diff_volume": float(abs(float(r["base_volume"]) - float(r["volume"])))
                })

    print(f"Total compared: {total_compared}")
    print(f"Total mismatched candles with diff > 0.01: {len(mismatched_candles)}")
    if mismatched_candles:
        df_mismatches = pd.DataFrame(mismatched_candles)
        print("\nTop 10 highest price discrepancies:")
        max_price_series = df_mismatches[["diff_open", "diff_high", "diff_low", "diff_close"]].max(axis=1)
        df_mismatches["max_price_diff"] = max_price_series
        df_sorted = df_mismatches.sort_values("max_price_diff", ascending=False)
        for _, r in df_sorted.head(10).iterrows():
            print(f"[{r['datetime_utc']}] max_price_diff={r['max_price_diff']:.2f}, high_diff={r['diff_high']:.2f}, vol_diff={r['diff_volume']:.4f}, raw=(O:{r['raw_open']}, H:{r['raw_high']}, L:{r['raw_low']}, C:{r['raw_close']}), vis=(O:{r['vis_open']}, H:{r['vis_high']}, L:{r['vis_low']}, C:{r['vis_close']})")

        print("\nDistribution across months:")
        print(df_mismatches["month"].value_counts())

if __name__ == "__main__":
    diagnose()
