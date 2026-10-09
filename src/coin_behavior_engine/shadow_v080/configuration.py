"""CBE-0.8.0 Shadow Collector Configuration & Safety Interlock.

Enforces:
- Hard safety interlocks: network disabled by default, live activation disabled, trading strictly prohibited.
- Resource constraints (RSS, buffer limits, disk footprints).
- Path isolation: completely separate from CBE-0.7.0 production storage.
- Protocol and experiment versioning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ShadowCollectorConfig:
    # 1. Hard Safety Interlocks (FAIL-SAFE DEFAULTS)
    network_enabled: bool = False
    live_shadow_enabled: bool = False
    trading_enabled: bool = False  # NEVER True; trading is permanently prohibited

    # 2. Market and Instrument Specification
    symbol: str = "BTCUSDT"
    interval: str = "5m"
    candle_interval_ms: int = 300_000

    # 3. Buffer and Warm-Up Invariants
    max_buffer_candles: int = 350
    min_warmup_bars: int = 72
    full_warmup_bars: int = 288

    # 4. Resource Budgets & Audit Policy
    max_rss_mb: float = 150.0
    max_network_requests_per_minute: int = 2
    max_event_log_mb: float = 250.0
    clock_skew_budget_ms: float = 1000.0
    full_audit_interval_cycles: int = 288  # Periodic full-chain audit once every 24 hours

    # 5. Metadata and Experiment Tracking
    experiment_id: str = "EXP-CBE-0.8.0-SHADOW-2026-V1"
    protocol_version: str = "CBE-PROTOCOL-0.8.0-V1"
    candidate_model_version: str = "CBE-0.8.0"

    # 6. Isolated Storage & Model Directories
    base_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[3])
    models_dir: Optional[Path] = None
    shadow_data_dir: Optional[Path] = None
    snapshot_dir: Path = field(init=False)
    prediction_dir: Path = field(init=False)
    outcome_dir: Path = field(init=False)
    audit_dir: Path = field(init=False)
    telemetry_dir: Path = field(init=False)

    def __post_init__(self):
        # Strict invariant: trading must NEVER be enabled
        if self.trading_enabled:
            raise ValueError("TRADING_ENABLED cannot be True: trading is strictly prohibited.")

        repo_root = Path(__file__).resolve().parents[3]
        if self.models_dir is None:
            self.models_dir = repo_root / "data" / "models"
        else:
            self.models_dir = Path(self.models_dir)

        if self.shadow_data_dir is None:
            self.shadow_data_dir = self.base_dir / "data" / "shadow_v080"
        else:
            self.shadow_data_dir = Path(self.shadow_data_dir)

        self.snapshot_dir = self.shadow_data_dir / "snapshots"
        self.prediction_dir = self.shadow_data_dir / "predictions"
        self.outcome_dir = self.shadow_data_dir / "outcomes"
        self.audit_dir = self.shadow_data_dir / "audit"
        self.telemetry_dir = self.shadow_data_dir / "telemetry"

    def ensure_directories(self) -> None:
        """Create isolated shadow data directories."""
        for d in [
            self.shadow_data_dir,
            self.snapshot_dir,
            self.prediction_dir,
            self.outcome_dir,
            self.audit_dir,
            self.telemetry_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["base_dir"] = str(self.base_dir)
        d["shadow_data_dir"] = str(self.shadow_data_dir)
        d["snapshot_dir"] = str(self.snapshot_dir)
        d["prediction_dir"] = str(self.prediction_dir)
        d["outcome_dir"] = str(self.outcome_dir)
        d["audit_dir"] = str(self.audit_dir)
        d["telemetry_dir"] = str(self.telemetry_dir)
        return d
