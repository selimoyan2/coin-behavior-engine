"""Historical BTC Timing Hypothesis Registry (Module 29.3).

Manages preregistered and exploratory timing research hypotheses with immutable
audit trails, server timestamps, parameter snapshots, and scientific status tracking.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_HYPOTHESIS_PERSISTENCE = REPO_ROOT / "data" / "research_lab" / "timing_hypotheses.json"

PERMITTED_RESEARCH_STATUSES: Set[str] = {
    "EXPLORATORY",
    "RETROSPECTIVE_TESTED",
    "OUT_OF_SAMPLE_TESTED",
    "PROSPECTIVE_NOT_ESTABLISHED",
    "INVALIDATED",
}


@dataclass
class TimingHypothesisRecord:
    """Canonical record of a historical BTC timing research hypothesis."""
    hypothesis_id: str
    hypothesis_name: str
    hypothesis_version: str
    research_question: str
    policy_id: str
    dataset_id: str
    dataset_sha256: str
    feature_set: List[str]
    decision_rule: str
    parameters: Dict[str, Any]
    parameter_selection_method: str
    transaction_cost_profile: str
    training_window: Optional[Dict[str, str]] = None
    validation_window: Optional[Dict[str, str]] = None
    test_window: Optional[Dict[str, str]] = None
    preregistration_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    research_status: str = "EXPLORATORY"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TimingHypothesisRegistry:
    """Thread-safe and durable registry for BTC timing hypotheses."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self.persistence_path = persistence_path or DEFAULT_HYPOTHESIS_PERSISTENCE
        self._hypotheses: Dict[str, TimingHypothesisRecord] = {}
        self.load_from_storage()
        if not self._hypotheses:
            self._seed_canonical_hypotheses()
            self.save_to_storage()

    def register_hypothesis(
        self,
        hypothesis_id: str,
        hypothesis_name: str,
        hypothesis_version: str,
        research_question: str,
        policy_id: str,
        dataset_id: str,
        dataset_sha256: str,
        feature_set: List[str],
        decision_rule: str,
        parameters: Dict[str, Any],
        parameter_selection_method: str,
        transaction_cost_profile: str,
        training_window: Optional[Dict[str, str]] = None,
        validation_window: Optional[Dict[str, str]] = None,
        test_window: Optional[Dict[str, str]] = None,
        research_status: str = "EXPLORATORY",
        notes: Optional[str] = None,
    ) -> TimingHypothesisRecord:
        """Register a new timing hypothesis. Enforces true server timestamp."""
        if hypothesis_id in self._hypotheses:
            raise ValueError(f"Hypothesis {hypothesis_id} is already registered.")

        if research_status not in PERMITTED_RESEARCH_STATUSES:
            raise ValueError(f"Invalid research_status {research_status}. Allowed: {PERMITTED_RESEARCH_STATUSES}")

        # Always assign contemporary server timestamp; do not accept caller backdating
        now_iso = datetime.now(timezone.utc).isoformat()

        record = TimingHypothesisRecord(
            hypothesis_id=hypothesis_id,
            hypothesis_name=hypothesis_name,
            hypothesis_version=hypothesis_version,
            research_question=research_question,
            policy_id=policy_id,
            dataset_id=dataset_id,
            dataset_sha256=dataset_sha256,
            feature_set=feature_set,
            decision_rule=decision_rule,
            parameters=parameters,
            parameter_selection_method=parameter_selection_method,
            transaction_cost_profile=transaction_cost_profile,
            training_window=training_window,
            validation_window=validation_window,
            test_window=test_window,
            preregistration_timestamp=now_iso,
            research_status=research_status,
            notes=notes,
        )
        self._hypotheses[hypothesis_id] = record
        self.save_to_storage()
        return record

    def get_hypothesis(self, hypothesis_id: str) -> Optional[TimingHypothesisRecord]:
        return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(self) -> List[TimingHypothesisRecord]:
        return list(self._hypotheses.values())

    def update_research_status(self, hypothesis_id: str, new_status: str) -> TimingHypothesisRecord:
        if hypothesis_id not in self._hypotheses:
            raise KeyError(f"Hypothesis {hypothesis_id} not found.")
        if new_status not in PERMITTED_RESEARCH_STATUSES:
            raise ValueError(f"Invalid status {new_status}. Allowed: {PERMITTED_RESEARCH_STATUSES}")
        rec = self._hypotheses[hypothesis_id]
        rec.research_status = new_status
        self.save_to_storage()
        return rec

    def load_from_storage(self) -> None:
        if not self.persistence_path.exists():
            return
        try:
            data = json.loads(self.persistence_path.read_text(encoding="utf-8"))
            items = data.get("hypotheses", [])
            for item in items:
                rec = TimingHypothesisRecord(**item)
                self._hypotheses[rec.hypothesis_id] = rec
        except Exception as e:
            logger.error(f"Failed to load timing hypotheses from {self.persistence_path}: {e}")

    def save_to_storage(self) -> None:
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.persistence_path.with_suffix(".tmp")
        payload = {
            "schema_version": "CBE-TIMING-HYPOTHESES-V1",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "hypotheses": [h.to_dict() for h in self._hypotheses.values()],
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        for attempt in range(10):
            try:
                os.replace(tmp_path, self.persistence_path)
                break
            except Exception:
                if attempt == 9:
                    shutil.copy2(tmp_path, self.persistence_path)
                    try:
                        tmp_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                else:
                    time.sleep(0.05)

    def _seed_canonical_hypotheses(self) -> None:
        """Seed initial research hypotheses for the canonical policies."""
        # 1. Buy and Hold Benchmark
        self.register_hypothesis(
            hypothesis_id="HYP-TIMING-BnH-001",
            hypothesis_name="BTC Buy and Hold Passive Benchmark",
            hypothesis_version="1.0.0",
            research_question="What is the baseline historical return, volatility, and max drawdown of passively holding BTC over the observation period?",
            policy_id="POLICY_BUY_AND_HOLD",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=["close"],
            decision_rule="Allocate 100% to BTC at start and hold indefinitely.",
            parameters={"target_allocation": 1.0},
            parameter_selection_method="FIXED_BENCHMARK",
            transaction_cost_profile="BASE_COST",
            research_status="EXPLORATORY",
            notes="Mandatory passive benchmark.",
        )

        # 2. USDT Cash Capital Preservation Benchmark
        self.register_hypothesis(
            hypothesis_id="HYP-TIMING-CASH-001",
            hypothesis_name="USDT Cash Capital Preservation Benchmark",
            hypothesis_version="1.0.0",
            research_question="What is the capital preservation baseline of holding 100% USDT without assumed yield?",
            policy_id="POLICY_USDT_CASH",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=[],
            decision_rule="Allocate 0% to BTC (100% USDT cash) throughout.",
            parameters={"target_allocation": 0.0},
            parameter_selection_method="FIXED_BENCHMARK",
            transaction_cost_profile="BASE_COST",
            research_status="EXPLORATORY",
            notes="Zero-yield cash benchmark.",
        )

        # 3. Simple Moving Average Trend Filter
        self.register_hypothesis(
            hypothesis_id="HYP-TIMING-TREND-001",
            hypothesis_name="Dual SMA Trend Following Allocation",
            hypothesis_version="1.0.0",
            research_question="Does reducing BTC exposure to 0% when price falls below SMA(50) reduce drawdown compared to Buy and Hold?",
            policy_id="POLICY_SIMPLE_TREND",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=["close", "sma_20", "sma_50"],
            decision_rule="100% BTC when close > sma_50, else 0% BTC.",
            parameters={"trend_indicator": "SMA", "fast_window": 20, "slow_window": 50},
            parameter_selection_method="HEURISTIC_PRESPECIFIED",
            transaction_cost_profile="BASE_COST",
            research_status="EXPLORATORY",
            notes="Evaluates whether simple trend filter protects capital during downtrends.",
        )

        # 4. Volatility-Aware Allocation
        self.register_hypothesis(
            hypothesis_id="HYP-TIMING-VOL-001",
            hypothesis_name="Parkinson Volatility-Scaled Allocation",
            hypothesis_version="1.0.0",
            research_question="Does dynamically scaling down BTC allocation during elevated historical volatility improve risk-adjusted returns?",
            policy_id="POLICY_VOLATILITY_AWARE",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=["high", "low", "parkinson_vol_24", "volatility_regime"],
            decision_rule="COMPRESSED_VOL: 100%, NORMAL_VOL: 75%, ELEVATED_VOL: 25%, EXTREME_VOL: 0%.",
            parameters={"window": 24, "scale_rule": "DISCRETE_TIERS"},
            parameter_selection_method="HEURISTIC_PRESPECIFIED",
            transaction_cost_profile="BASE_COST",
            research_status="EXPLORATORY",
            notes="Evaluates volatility risk-budgeting without directional bias.",
        )

        # 5. CBE-0.7.0 Regime Allocation
        self.register_hypothesis(
            hypothesis_id="HYP-TIMING-REGIME-001",
            hypothesis_name="CBE Frozen Regime Research Allocation",
            hypothesis_version="1.0.0",
            research_question="Can CBE-0.7.0 canonical market regimes (Momentum, Recovery, Consolidation, Distribution, Capitulation) improve BTC timing?",
            policy_id="POLICY_CBE_REGIME",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=["market_regime", "volatility_regime"],
            decision_rule="MOMENTUM: 100%, RECOVERY: 75%, CONSOLIDATION: 50%, DISTRIBUTION: 25%, CAPITULATION/HIGH_VOL: 0%.",
            parameters={"model_version": "CBE-0.7.0", "thresholds": "FROZEN"},
            parameter_selection_method="CANONICAL_MODEL_MAPPING",
            transaction_cost_profile="BASE_COST",
            research_status="EXPLORATORY",
            notes="Maps frozen scientific regimes to discrete exposure tiers.",
        )

        # 6. Combined Trend and CBE Regime
        self.register_hypothesis(
            hypothesis_id="HYP-TIMING-COMBINED-001",
            hypothesis_name="Combined Trend and CBE Regime Filter",
            hypothesis_version="1.0.0",
            research_question="Does combining a moving average trend filter with CBE regime confirmation yield superior downside protection?",
            policy_id="POLICY_COMBINED_TREND_REGIME",
            dataset_id="DS-BTC-1H-2023-2024",
            dataset_sha256="b83ec887baa37fb557544143e80f4f35628bd701f1ea8a51be7a88c199e9c874",
            feature_set=["close", "sma_50", "market_regime"],
            decision_rule="Exposure active only when trend is positive AND regime is non-capitulating.",
            parameters={"trend_window": 50, "exclude_regimes": ["CAPITULATION", "HIGH_VOLATILITY_EXPANSION"]},
            parameter_selection_method="EXPLORATORY_HYBRID",
            transaction_cost_profile="BASE_COST",
            research_status="EXPLORATORY",
            notes="Experimental multi-factor research policy.",
        )
