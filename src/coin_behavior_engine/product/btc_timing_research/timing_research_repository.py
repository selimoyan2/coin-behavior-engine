"""Timing Research Repository & Persistence Engine (Module 29.11).

Persists and indexes historical BTC timing experiments, paper portfolio runs,
equity curves, and trade ledgers with atomic file operations and restart recovery:
1. Prevents duplicate experiment IDs.
2. Atomically persists experiment JSON files.
3. Maintains a durable experiments index for fast querying without re-reading all files.
4. Survives container and process restarts.
5. Employs Windows/Linux safe atomic file replacements.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTS_DIR = REPO_ROOT / "data" / "research_lab" / "btc_timing_experiments"
INDEX_FILE = EXPERIMENTS_DIR / "experiments_index.json"


@dataclass
class TimingExperimentRecord:
    """Authoritative metadata and results of a completed timing experiment."""
    experiment_id: str
    created_at_utc: str
    policy_id: str
    policy_name: str
    policy_version: str
    dataset_id: str
    dataset_sha256: str
    model_version: str
    parameter_snapshot: Dict[str, Any]
    cost_profile_id: str
    initial_capital_usdt: float
    ending_equity_usdt: float
    net_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    trade_count: int
    evaluation_start_utc: str
    evaluation_end_utc: str
    execution_convention: str
    research_status: str  # EXPERIMENT_CONFIGURED, HISTORICAL_SIMULATION_COMPLETED, EXPLORATORY_RESULT
    metrics_summary: Dict[str, Any]
    benchmark_comparison: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TimingResearchRepository:
    """Thread-safe persistent store for BTC timing research experiments."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or EXPERIMENTS_DIR
        self.index_file = self.base_dir / "experiments_index.json"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            payload = {
                "schema_version": "CBE-TIMING-EXPERIMENTS-INDEX-V1",
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "experiments": [],
            }
            self._write_json_atomic(self.index_file, payload)

    @staticmethod
    def _write_json_atomic(target_path: Path, data: Any) -> None:
        """Atomically persist JSON with Windows-safe retry."""
        tmp = target_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        for attempt in range(10):
            try:
                os.replace(tmp, target_path)
                break
            except Exception:
                if attempt == 9:
                    shutil.copy2(tmp, target_path)
                    try:
                        tmp.unlink(missing_ok=True)
                    except Exception:
                        pass
                else:
                    time.sleep(0.05)

    def save_experiment(
        self,
        record: TimingExperimentRecord,
        equity_curve: List[Any],
        trades: List[Any],
    ) -> Path:
        """Persist full experiment record, equity curve points, and trades."""
        exp_file = self.base_dir / f"{record.experiment_id}.json"
        if exp_file.exists():
            raise FileExistsError(f"Experiment {record.experiment_id} already exists on disk.")

        # Serialize equity points and trades
        serialized_equity = [pt.to_dict() if hasattr(pt, "to_dict") else pt for pt in equity_curve]
        serialized_trades = [tr.to_dict() if hasattr(tr, "to_dict") else tr for tr in trades]

        payload = {
            "experiment_id": record.experiment_id,
            "metadata": record.to_dict(),
            "equity_curve": serialized_equity,
            "trades": serialized_trades,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self._write_json_atomic(exp_file, payload)

        # Update index
        self._update_index(record)
        return exp_file

    def _update_index(self, record: TimingExperimentRecord) -> None:
        try:
            index_data = json.loads(self.index_file.read_text(encoding="utf-8"))
        except Exception:
            index_data = {"schema_version": "CBE-TIMING-EXPERIMENTS-INDEX-V1", "experiments": []}

        experiments = [e for e in index_data.get("experiments", []) if e.get("experiment_id") != record.experiment_id]
        experiments.append(record.to_dict())
        index_data["experiments"] = experiments
        index_data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        self._write_json_atomic(self.index_file, index_data)

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full experiment payload including equity curve and trades."""
        exp_file = self.base_dir / f"{experiment_id}.json"
        if not exp_file.exists():
            return None
        try:
            return json.loads(exp_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Error reading experiment {exp_file}: {e}")
            return None

    def list_experiments(self) -> List[Dict[str, Any]]:
        """List all experiment summary records from the durable index."""
        if not self.index_file.exists():
            return []
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            return data.get("experiments", [])
        except Exception as e:
            logger.error(f"Error reading index {self.index_file}: {e}")
            return []
