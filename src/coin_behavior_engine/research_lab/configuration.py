"""Configuration dataclasses and safety controls for CBE Research Lab.

Sprint 11.03: Market Behavior Research Lab.
Enforces non-negotiable safety interlocks: real trading and production execution remain permanently blocked.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


# Non-negotiable research safety constants
RESEARCH_LAB_ACTIVE: bool = True
RESEARCH_TRADING_ENABLED: bool = False
RESEARCH_PROSPECTIVE_OBSERVATION: bool = False
RESEARCH_APPROVAL_4_AUTHORIZED: bool = False


@dataclass
class ResearchLabConfig:
    """Central configuration for research lab and historical simulation."""
    symbol: str = "BTCUSDT"
    primary_interval: str = "1m"
    derived_intervals: List[str] = field(default_factory=lambda: ["5m", "15m", "1h", "4h"])
    
    # Financial simulation assumptions (HYPOTHETICAL ONLY)
    initial_capital_usdt: float = 10_000.0
    taker_fee_pct: float = 0.0010  # 0.10% standard Binance spot taker
    maker_fee_pct: float = 0.00075  # 0.075% BNB discount maker
    slippage_pct: float = 0.0005  # 0.05% realistic spot slippage assumption
    max_position_size_pct: float = 0.25  # Max 25% portfolio allocated per position
    risk_per_trade_pct: float = 0.02  # Max 2% capital risk per trade
    default_stop_loss_atr_mult: float = 1.5
    default_take_profit_atr_mult: float = 3.0
    max_holding_bars_5m: int = 24  # Max 24 bars (2 hours on 5m)
    
    # Directory paths
    data_dir: Path = Path("data/research_lab")
    output_dir: Path = Path("research_outputs")
    historical_archive_dir: Path = Path("data/historical")
    live_capture_dir: Path = Path("data/shadow_v080")
    
    # Network & Rate-Limiting
    allow_network_download: bool = True
    binance_base_url: str = "https://api.binance.com/api/v3"
    request_timeout_seconds: float = 10.0
    max_retries: int = 3
    retry_backoff_base_seconds: float = 1.0
    rate_limit_pause_seconds: float = 0.1
    
    # Analysis & Pattern parameters
    min_pattern_samples: int = 3
    volatility_lookback_bars: int = 24
    atr_period: int = 14
    volume_lookback_bars: int = 20
    
    # MANDATORY SAFETY GATES (HARDCODED INVARIANTS)
    trading_enabled: bool = False
    approval_4_authorized: bool = False
    prospective_scoring_enabled: bool = False

    def __post_init__(self):
        # Enforce fail-closed safety invariants
        if self.trading_enabled:
            raise ValueError("SAFETY INVARIANT VIOLATION: Real trading cannot be enabled in Research Lab.")
        if self.approval_4_authorized:
            raise ValueError("SAFETY INVARIANT VIOLATION: Approval 4 cannot be enabled in Research Lab.")
        if self.prospective_scoring_enabled:
            raise ValueError("SAFETY INVARIANT VIOLATION: Prospective scoring cannot be enabled in Research Lab.")
        
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
