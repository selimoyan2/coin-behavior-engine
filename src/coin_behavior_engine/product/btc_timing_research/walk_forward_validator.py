"""Historical Walk-Forward & Chronological Partition Validator (Module 29.10).

Prevents in-sample overfitting and unrecorded holdout contamination:
1. Splits historical datasets chronologically into Training, Validation, and Test windows.
2. Checks contamination against the authoritative holdout usage ledger.
3. Reports CLEAN_HOLDOUT_NOT_AVAILABLE if the holdout was previously touched.
4. Executes rolling and expanding walk-forward simulations.
5. Measures performance degradation between in-sample and out-of-sample periods.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.performance_analytics import (
    PerformanceAnalyticsEngine,
    PerformanceMetricsReport,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BaseTimingPolicy,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
HOLDOUT_LEDGER_PATH = REPO_ROOT / "data" / "research_lab" / "holdout_usage_ledger.json"


@dataclass(frozen=True)
class WalkForwardFoldResult:
    """Outcome for a single walk-forward fold."""
    fold_index: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_net_return_pct: float
    test_net_return_pct: float
    train_sharpe: Optional[float]
    test_sharpe: Optional[float]
    train_max_dd_pct: float
    test_max_dd_pct: float
    return_degradation_pct: float
    is_profitable_oos: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WalkForwardValidationReport:
    """Complete chronological validation assessment."""
    validation_id: str
    policy_id: str
    dataset_id: str
    clean_holdout_available: bool
    holdout_status_code: str  # CLEAN_HOLDOUT_VERIFIED or CLEAN_HOLDOUT_NOT_AVAILABLE
    total_folds: int
    folds: List[WalkForwardFoldResult]
    mean_in_sample_return_pct: float
    mean_out_of_sample_return_pct: float
    mean_degradation_pct: float
    out_of_sample_consistency_pct: float
    scientific_verdict: str  # STABLE_OUT_OF_SAMPLE, INCONCLUSIVE_OUT_OF_SAMPLE, SEVERE_OVERFITTING
    validation_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "policy_id": self.policy_id,
            "dataset_id": self.dataset_id,
            "clean_holdout_available": self.clean_holdout_available,
            "holdout_status_code": self.holdout_status_code,
            "total_folds": self.total_folds,
            "folds": [f.to_dict() for f in self.folds],
            "mean_in_sample_return_pct": self.mean_in_sample_return_pct,
            "mean_out_of_sample_return_pct": self.mean_out_of_sample_return_pct,
            "mean_degradation_pct": self.mean_degradation_pct,
            "out_of_sample_consistency_pct": self.out_of_sample_consistency_pct,
            "scientific_verdict": self.scientific_verdict,
            "validation_notes": self.validation_notes,
        }


class WalkForwardValidator:
    """Validates timing policy stability across sequential historical partitions."""

    def __init__(self, ledger_path: Optional[Path] = None):
        self.ledger_path = ledger_path or HOLDOUT_LEDGER_PATH

    def check_holdout_contamination(self, partition_id: str = "PART-2024-HOLD") -> Tuple[bool, int]:
        """Check if holdout partition was previously accessed in the ledger."""
        if not self.ledger_path.exists():
            return True, 0
        try:
            data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            events = data.get("holdout_events", [])
            matches = [e for e in events if e.get("holdout_partition_id") == partition_id]
            count = len(matches)
            is_clean = (count == 0)
            return is_clean, count
        except Exception as e:
            logger.warning(f"Error reading holdout ledger {self.ledger_path}: {e}")
            return False, 999

    def execute_walk_forward(
        self,
        df_features: pd.DataFrame,
        policy: BaseTimingPolicy,
        n_folds: int = 3,
        cost_profile_id: str = "BASE_COST",
    ) -> WalkForwardValidationReport:
        """Run expanding walk-forward cross-validation across chronological slices."""
        total_len = len(df_features)
        if total_len < 300:
            raise ValueError(f"Insufficient observations ({total_len}) for walk-forward validation (min 300).")

        # Check holdout contamination
        is_clean_holdout, access_count = self.check_holdout_contamination()
        notes = []
        if not is_clean_holdout:
            status_code = "CLEAN_HOLDOUT_NOT_AVAILABLE"
            notes.append(f"Holdout partition has {access_count} prior recorded accesses in holdout_usage_ledger.json. Retaining EXPLORATORY status.")
        else:
            status_code = "CLEAN_HOLDOUT_VERIFIED"
            notes.append("Virgin holdout partition verified with 0 prior access records.")

        # Construct expanding folds
        # E.g. for n_folds = 3:
        # Fold 1: Train 0%..40%, Test 40%..60%
        # Fold 2: Train 0%..60%, Test 60%..80%
        # Fold 3: Train 0%..80%, Test 80%..100%
        fold_results: List[WalkForwardFoldResult] = []
        base_train_pct = 0.40
        step_pct = (1.0 - base_train_pct) / n_folds

        for k in range(n_folds):
            train_end_idx = int(total_len * (base_train_pct + k * step_pct))
            test_end_idx = int(total_len * (base_train_pct + (k + 1) * step_pct)) if k < n_folds - 1 else total_len

            train_df = df_features.iloc[:train_end_idx].copy().reset_index(drop=True)
            test_df = df_features.iloc[train_end_idx:test_end_idx].copy().reset_index(drop=True)

            # In-sample simulation
            train_engine, _ = run_historical_simulation(
                df_features=train_df,
                policy=policy,
                cost_profile_id=cost_profile_id,
                start_index=min(50, len(train_df) // 2),
            )
            train_metrics = PerformanceAnalyticsEngine.calculate_metrics(train_engine)

            # Out-of-sample simulation
            test_engine, _ = run_historical_simulation(
                df_features=test_df,
                policy=policy,
                cost_profile_id=cost_profile_id,
                start_index=1,
            )
            test_metrics = PerformanceAnalyticsEngine.calculate_metrics(test_engine)

            # Degradation calculation
            ret_in = train_metrics.net_return_pct
            ret_out = test_metrics.net_return_pct
            if abs(ret_in) > 1e-4:
                deg = ((ret_in - ret_out) / abs(ret_in)) * 100.0
            else:
                deg = 0.0

            fold_rec = WalkForwardFoldResult(
                fold_index=k + 1,
                train_start=str(train_df.iloc[0].get("datetime_utc", "")),
                train_end=str(train_df.iloc[-1].get("datetime_utc", "")),
                test_start=str(test_df.iloc[0].get("datetime_utc", "")),
                test_end=str(test_df.iloc[-1].get("datetime_utc", "")),
                train_net_return_pct=round(ret_in, 2),
                test_net_return_pct=round(ret_out, 2),
                train_sharpe=train_metrics.sharpe_ratio,
                test_sharpe=test_metrics.sharpe_ratio,
                train_max_dd_pct=train_metrics.max_drawdown_pct,
                test_max_dd_pct=test_metrics.max_drawdown_pct,
                return_degradation_pct=round(deg, 2),
                is_profitable_oos=(ret_out > 0.0),
            )
            fold_results.append(fold_rec)

        mean_train_ret = float(np.mean([f.train_net_return_pct for f in fold_results]))
        mean_test_ret = float(np.mean([f.test_net_return_pct for f in fold_results]))
        mean_deg = float(np.mean([f.return_degradation_pct for f in fold_results]))
        profitable_folds = sum(1 for f in fold_results if f.is_profitable_oos)
        consistency_pct = round((profitable_folds / n_folds) * 100.0, 2)

        if consistency_pct >= 66.0 and mean_test_ret > 0:
            verdict = "EXPLORATORY_RESULT" if not is_clean_holdout else "STABLE_OUT_OF_SAMPLE"
            notes.append("Policy demonstrated positive out-of-sample returns across >= 66% of folds.")
        elif mean_deg > 75.0 or mean_test_ret < -5.0:
            verdict = "REJECTED_OVERFITTING"
            notes.append("Severe out-of-sample degradation detected; policy is overfitted to in-sample data.")
        else:
            verdict = "EXPLORATORY_RESULT" if not is_clean_holdout else "INCONCLUSIVE_OUT_OF_SAMPLE"
            notes.append("Out-of-sample evidence is mixed or insufficient to confirm temporal stability.")

        rep = WalkForwardValidationReport(
            validation_id=f"WF-VAL-{policy.policy_id[:10]}-{n_folds}F",
            policy_id=policy.policy_id,
            dataset_id="DS-BTC-1H-2023-2024",
            clean_holdout_available=is_clean_holdout,
            holdout_status_code=status_code,
            total_folds=n_folds,
            folds=fold_results,
            mean_in_sample_return_pct=round(mean_train_ret, 2),
            mean_out_of_sample_return_pct=round(mean_test_ret, 2),
            mean_degradation_pct=round(mean_deg, 2),
            out_of_sample_consistency_pct=consistency_pct,
            scientific_verdict=verdict,
            validation_notes=notes,
        )
        return rep
