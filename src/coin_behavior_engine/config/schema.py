"""Configuration schema definitions for research settings."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AssetConfig(BaseModel):
    symbol: str = "BTCUSDT"
    base_asset: str = "BTC"
    quote_asset: str = "USDT"
    primary_timeframe: str = "5m"
    derived_timeframes: List[str] = Field(default_factory=lambda: ["15m", "1h", "4h", "1d"])


class TimeRangeConfig(BaseModel):
    start_utc: str = "2026-01-01T00:00:00Z"
    end_utc: Optional[str] = None


class DataSourceConfig(BaseModel):
    provider: str = "binance"
    base_url: str = "https://api.binance.com"
    klines_endpoint: str = "/api/v3/klines"
    request_limit: int = 1000
    rate_limit_pause_sec: float = 0.1
    max_retries: int = 5
    timeout_sec: int = 15


class PathsConfig(BaseModel):
    raw_dir: str = "data/raw"
    normalized_dir: str = "data/normalized"
    derived_dir: str = "data/derived"
    reports_dir: str = "data/reports"
    charts_dir: str = "data/reports/charts"


class ValidationConfig(BaseModel):
    max_allowed_consecutive_missing: int = 12
    strict_ohlc_check: bool = True
    allow_zero_volume: bool = False


class WindowsConfig(BaseModel):
    short: int = 12
    medium: int = 36
    long: int = 144
    baseline: int = 288
    extended: int = 2016


class AdaptiveNormalizationConfig(BaseModel):
    rolling_distribution_window: int = 288
    mad_multiplier: float = 1.4826


class FeaturesConfig(BaseModel):
    windows: WindowsConfig = Field(default_factory=WindowsConfig)
    adaptive_normalization: AdaptiveNormalizationConfig = Field(default_factory=AdaptiveNormalizationConfig)


class EventWeightsConfig(BaseModel):
    return_abnormality: float = 0.35
    range_abnormality: float = 0.25
    volume_abnormality: float = 0.20
    volatility_expansion: float = 0.20


class EventWindowsConfig(BaseModel):
    pre: List[str] = Field(default_factory=lambda: ["1h", "4h", "12h", "24h", "3d", "7d"])
    post: List[str] = Field(default_factory=lambda: ["1h", "4h", "12h", "24h", "3d", "7d"])


class EventsConfig(BaseModel):
    weights: EventWeightsConfig = Field(default_factory=EventWeightsConfig)
    candidate_percentile_threshold: float = 0.95
    significant_event_percentile_threshold: float = 0.99
    extreme_event_percentile_threshold: float = 0.998
    failed_expansion_max_followthrough_pct: float = 0.003
    windows: EventWindowsConfig = Field(default_factory=EventWindowsConfig)


class RegimesConfig(BaseModel):
    volatility_low_percentile: float = 0.30
    volatility_high_percentile: float = 0.70
    trend_slope_quantile: float = 0.65
    trend_strength_min: float = 0.50
    min_regime_duration_bars: int = 12


class MultiTimeframeConfig(BaseModel):
    linkage_tolerance_minutes: int = 30


class ReproducibilityConfig(BaseModel):
    seed: int = 42


class ResearchConfig(BaseModel):
    asset: AssetConfig = Field(default_factory=AssetConfig)
    time_range: TimeRangeConfig = Field(default_factory=TimeRangeConfig)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    events: EventsConfig = Field(default_factory=EventsConfig)
    regimes: RegimesConfig = Field(default_factory=RegimesConfig)
    multitimeframe: MultiTimeframeConfig = Field(default_factory=MultiTimeframeConfig)
    reproducibility: ReproducibilityConfig = Field(default_factory=ReproducibilityConfig)
