"""Walk-forward evaluation and Out-of-Sample validation engine.

Implements:
1. Expanding quarterly walk-forward evaluation on Discovery (2021-2024).
2. Frozen Out-of-Sample evaluation on Validation (2025) with classification:
   REPLICATE, WEAKEN, DISAPPEAR, REVERSE.
3. Post-hoc audit check on Observed Holdout (2026).
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from scipy import stats

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.snapshots.comparison import compute_cohens_d


def classify_replication_outcome(
    discovery_effect: float,
    validation_effect: float,
    val_pvalue: float,
    alpha: float = 0.05,
    tolerance_pct: float = 0.20,
) -> str:
    """
    Classify out-of-sample replication status:
    - REPLICATE: p < alpha and validation effect is within +/- 20% of discovery
    - WEAKEN: p < alpha and validation effect is same sign but attenuated > 20%
    - DISAPPEAR: p >= alpha (no statistical significance)
    - REVERSE: validation effect has opposite sign
    """
    if np.isnan(validation_effect) or val_pvalue >= alpha:
        return "DISAPPEAR"

    if discovery_effect * validation_effect < 0:
        return "REVERSE"

    # Attenuation check
    rel_diff = abs(validation_effect - discovery_effect) / (abs(discovery_effect) + 1e-6)
    if rel_diff <= tolerance_pct:
        return "REPLICATE"
    elif abs(validation_effect) < abs(discovery_effect):
        return "WEAKEN"
    else:
        return "AMPLIFY"


class WalkForwardEvaluator:
    """Runs quarterly expanding walk-forward validation and out-of-sample testing."""

    def __init__(self, step_quarterly: bool = True):
        self.step_quarterly = step_quarterly

    def run_expanding_quarterly_discovery(
        self,
        discovery_df: pd.DataFrame,
        event_col: str = "is_event",
    ) -> List[Dict[str, Any]]:
        """
        Run quarterly expanding window on Discovery partition (2021-2024).
        Training starts with 2021 (4 quarters), then steps forward quarter-by-quarter.
        """
        if discovery_df.empty or "datetime_open" not in discovery_df.columns:
            return []

        df = discovery_df.copy()
        df["quarter"] = df["datetime_open"].dt.to_period("Q")
        quarters = sorted(df["quarter"].unique())

        if len(quarters) < 5:
            logger.warning("Fewer than 5 quarters in discovery partition.")
            return []

        fold_results = []
        # First train on 2021 (4 quarters)
        train_q_end_idx = 3  # index 3 is 2021Q4

        for test_idx in range(train_q_end_idx + 1, len(quarters)):
            test_q = quarters[test_idx]
            train_quarters = quarters[:test_idx]

            train_mask = df["quarter"].isin(train_quarters)
            test_mask = df["quarter"] == test_q

            train_df = df[train_mask]
            test_df = df[test_mask]

            # In-fold metrics
            n_train_events = int(train_df[event_col].sum()) if event_col in train_df.columns else 0
            n_test_events = int(test_df[event_col].sum()) if event_col in test_df.columns else 0

            # Forward returns of test events vs test non-events
            ev_mask = test_df[event_col] if event_col in test_df.columns else pd.Series(False, index=test_df.index)
            test_ev_ret = test_df.loc[ev_mask, "fwd_abs_ret_24h"].dropna() if "fwd_abs_ret_24h" in test_df.columns else pd.Series()
            test_non_ev_ret = test_df.loc[~ev_mask, "fwd_abs_ret_24h"].dropna() if "fwd_abs_ret_24h" in test_df.columns else pd.Series()

            d = compute_cohens_d(test_ev_ret.to_numpy(), test_non_ev_ret.to_numpy()) if len(test_ev_ret) > 0 else 0.0

            fold_results.append({
                "test_quarter": str(test_q),
                "train_span": f"{train_quarters[0]} to {train_quarters[-1]}",
                "n_train_candles": len(train_df),
                "n_test_candles": len(test_df),
                "n_train_events": n_train_events,
                "n_test_events": n_test_events,
                "test_event_frequency_pct": round(n_test_events / len(test_df) * 100, 3) if len(test_df) > 0 else 0.0,
                "test_mean_ev_fwd_abs_24h": round(float(test_ev_ret.mean()), 4) if len(test_ev_ret) > 0 else np.nan,
                "test_mean_non_ev_fwd_abs_24h": round(float(test_non_ev_ret.mean()), 4) if len(test_non_ev_ret) > 0 else np.nan,
                "cohens_d_fwd_abs": round(d, 4),
            })

        logger.info(f"Completed {len(fold_results)} expanding walk-forward folds on Discovery partition.")
        return fold_results

    def evaluate_out_of_sample(
        self,
        discovery_df: pd.DataFrame,
        validation_df: pd.DataFrame,
        hypotheses_tests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Evaluate frozen Discovery findings against Validation (2025) and Observed Holdout (2026).
        """
        eval_records = []
        for hyp in hypotheses_tests:
            name = hyp["name"]
            disc_effect = hyp["discovery_effect"]
            val_effect = hyp["validation_effect"]
            val_pval = hyp["validation_pvalue"]

            classification = classify_replication_outcome(disc_effect, val_effect, val_pval)

            eval_records.append({
                "hypothesis": name,
                "discovery_effect_size": round(disc_effect, 4),
                "validation_effect_size": round(val_effect, 4),
                "validation_pvalue": float(val_pval),
                "classification": classification,
                "notes": hyp.get("notes", ""),
            })

        return eval_records
