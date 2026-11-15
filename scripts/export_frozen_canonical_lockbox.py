"""Export frozen canonical lockbox for UnifiedMarketStateEngine (CBE-0.7.0).

Saves fitted parameters and models to data/models/cbe_070_canonical_frozen_lockbox.pkl
and metadata to data/models/cbe_070_canonical_frozen_lockbox_manifest.json.
Guarantees zero runtime fitting overhead and strictly frozen weights.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pickle
import pandas as pd

from coin_behavior_engine.market_state.engine import UnifiedMarketStateEngine
from coin_behavior_engine.product.btc_timing_research.canonical_model_research_bridge import (
    CanonicalModelResearchBridge,
    FROZEN_DISCOVERY_THRESHOLDS,
)

def export_canonical_lockbox():
    disc_path = Path("data/historical/BTCUSDT-1h-2023-10-to-2024-11.parquet")
    if not disc_path.exists():
        raise FileNotFoundError(f"Discovery dataset not found: {disc_path}")

    df_disc = pd.read_parquet(disc_path).iloc[:2000]
    feats = CanonicalModelResearchBridge.extract_features(df_disc)

    engine = UnifiedMarketStateEngine()
    engine.fit_discovery(feats)

    # Pack fitted state
    state = {
        "model_version": engine.model_version,
        "is_fitted": engine.is_fitted,
        "tail_thresholds_95": engine.tail_thresholds_95,
        "tail_thresholds_99": engine.tail_thresholds_99,
        "jump_thresholds": engine.jump_thresholds,
        "vol_models": engine.vol_models,
        "tail_models": engine.tail_models,
        "jump_models": engine.jump_models,
        "scalers": engine.scalers,
        "state_priors": engine.state_priors,
        "state_transition_matrix": engine.state_transition_matrix,
        "discovery_centroid": engine.discovery_centroid,
        "discovery_cov_inv": engine.discovery_cov_inv,
        "calibration_timestamp": "2023-12-23T07:00:00Z",
        "discovery_bars": 2000,
        "discovery_start_utc": "2023-10-01T00:00:00Z",
        "discovery_end_utc": "2023-12-23T07:00:00Z",
    }

    out_pkl = Path("data/models/cbe_070_canonical_frozen_lockbox.pkl")
    with open(out_pkl, "wb") as f:
        pickle.dump(state, f)

    manifest = {
        "model_version": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "lockbox_file": str(out_pkl),
        "calibration_partition": "data/historical/BTCUSDT-1h-2023-10-to-2024-11.parquet (bars 0:2000)",
        "discovery_start_utc": "2023-10-01T00:00:00Z",
        "discovery_end_utc": "2023-12-23T07:00:00Z",
        "total_bars": 2000,
        "frozen_thresholds": FROZEN_DISCOVERY_THRESHOLDS,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    out_manifest = Path("data/models/cbe_070_canonical_frozen_lockbox_manifest.json")
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Exported frozen lockbox to {out_pkl} and {out_manifest}")

if __name__ == "__main__":
    export_canonical_lockbox()
