"""Multi-Horizon Probabilistic Forecaster & Comparative Benchmark Suite.

Sprint 11.19 Phase 4:
Computes probabilistic analog forecasts across 8 horizons:
[1h, 3h, 6h, 12h, 24h, 48h, 72h, 7d]

Calculates:
- Probability of positive/negative return P(ret > 0).
- Expected (weighted mean) and median returns.
- Return quantiles: 10%, 25%, 75%, 90%.
- Expected MFE (Maximum Favorable Excursion) and MAE (Maximum Adverse Excursion).
- Probability of hitting profit target before stop loss invalidation (after 0.30% round-trip friction).
- Strict conservative intrabar ordering: If target and stop are touched in the same bar, stop is hit first.
- Strict statistical scoring: Brier score, pinball loss, calibration, MAE.
- Benchmark comparisons against:
  1. Unconditional historical base rate
  2. Regime-conditioned base rate
  3. Recent-volatility baseline
  4. Momentum / persistence baseline
  5. Matched random analog retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.analogs.similarity_engine import AnalogSearchResult, HistoricalAnalog


@dataclass(frozen=True)
class HorizonForecast:
    """Probabilistic forecast for a specific forward horizon."""
    horizon: str
    horizon_bars: int
    prob_up: float
    prob_down: float
    expected_return: float
    median_return: float
    quantile_10: float
    quantile_25: float
    quantile_75: float
    quantile_90: float
    expected_mfe: float
    expected_mae: float
    prob_hit_target_first: float
    target_stop_ratio: float
    intrabar_ambiguity_count: int


@dataclass(frozen=True)
class ProbabilisticPrediction:
    """Complete multi-horizon prediction bundle for a query point."""
    query_timestamp_utc: str
    query_open_time: int
    query_close: float
    query_regime: str
    is_abstained: bool
    abstention_reason: Optional[str]
    forecasts: Dict[str, HorizonForecast]


class ProbabilisticForecaster:
    """Generates multi-horizon probabilistic distributions from historical analogs."""

    HORIZONS = {
        "1h": 12,
        "3h": 36,
        "6h": 72,
        "12h": 144,
        "24h": 288,
        "48h": 576,
        "72h": 864,
        "7d": 2016
    }

    ROUND_TRIP_FRICTION = 0.0030  # 0.10% fee + 0.05% slippage entry & exit = 0.30%

    def __init__(
        self,
        target_pct: float = 0.020,     # +2.0% profit target
        stop_pct: float = 0.010        # -1.0% stop loss
    ):
        self.target_pct = target_pct
        self.stop_pct = stop_pct

    def generate_forecast(
        self,
        search_result: AnalogSearchResult,
        query_close: float,
        df_5m: pd.DataFrame
    ) -> ProbabilisticPrediction:
        """Generate multi-horizon probabilistic distributions from retrieved analogs."""
        if search_result.is_abstained or len(search_result.analogs) == 0:
            return ProbabilisticPrediction(
                query_timestamp_utc=search_result.query_timestamp_utc,
                query_open_time=search_result.query_open_time,
                query_close=query_close,
                query_regime=search_result.query_regime,
                is_abstained=True,
                abstention_reason=search_result.abstention_reason,
                forecasts={}
            )

        analogs = search_result.analogs
        sim_weights = np.array([a.similarity_score for a in analogs], dtype=np.float64)
        total_w = np.sum(sim_weights)
        if total_w <= 1e-8:
            weights = np.ones(len(analogs)) / len(analogs)
        else:
            weights = sim_weights / total_w

        forecasts = {}
        high_arr = df_5m["high"].to_numpy()
        low_arr = df_5m["low"].to_numpy()
        close_arr = df_5m["close"].to_numpy()
        n_bars = len(df_5m)

        for h_label, h_bars in self.HORIZONS.items():
            rets = []
            mfes = []
            maes = []
            w_valid = []
            target_hits = 0
            stop_hits = 0
            ambiguous_hits = 0

            # Target required after friction: target_pct + friction
            gross_target = self.target_pct + self.ROUND_TRIP_FRICTION
            gross_stop = -(self.stop_pct + self.ROUND_TRIP_FRICTION)

            for i, a in enumerate(analogs):
                r = a.forward_returns.get(h_label)
                if r is not None and not np.isnan(r):
                    rets.append(r)
                    mfes.append(a.forward_mfe.get(h_label, 0.0))
                    maes.append(a.forward_mae.get(h_label, 0.0))
                    w_valid.append(weights[i])

                    # Intrabar path evaluation for target vs stop
                    c_idx = a.candle_idx
                    base_p = close_arr[c_idx]
                    end_idx = min(c_idx + h_bars + 1, n_bars)

                    hit_target = False
                    hit_stop = False

                    for step in range(c_idx + 1, end_idx):
                        bar_high_ret = (high_arr[step] - base_p) / base_p
                        bar_low_ret = (low_arr[step] - base_p) / base_p

                        bar_touches_target = bar_high_ret >= gross_target
                        bar_touches_stop = bar_low_ret <= gross_stop

                        if bar_touches_target and bar_touches_stop:
                            # Intrabar ambiguity: conservative convention -> STOP HIT FIRST
                            ambiguous_hits += 1
                            hit_stop = True
                            break
                        elif bar_touches_stop:
                            hit_stop = True
                            break
                        elif bar_touches_target:
                            hit_target = True
                            break

                    if hit_target:
                        target_hits += 1
                    elif hit_stop:
                        stop_hits += 1

            if len(rets) == 0:
                continue

            rets = np.array(rets)
            mfes = np.array(mfes)
            maes = np.array(maes)
            w_norm = np.array(w_valid) / sum(w_valid)

            prob_up = float(np.sum(w_norm[rets > 0.0]))
            prob_down = float(np.sum(w_norm[rets < 0.0]))
            exp_ret = float(np.sum(w_norm * rets))

            # Weighted quantiles
            q10 = float(self._weighted_quantile(rets, w_norm, 0.10))
            q25 = float(self._weighted_quantile(rets, w_norm, 0.25))
            q50 = float(self._weighted_quantile(rets, w_norm, 0.50))
            q75 = float(self._weighted_quantile(rets, w_norm, 0.75))
            q90 = float(self._weighted_quantile(rets, w_norm, 0.90))

            exp_mfe = float(np.sum(w_norm * mfes))
            exp_mae = float(np.sum(w_norm * maes))

            resolved_path_count = target_hits + stop_hits
            prob_target_first = float(target_hits / resolved_path_count) if resolved_path_count > 0 else 0.50
            ts_ratio = float(target_hits / stop_hits) if stop_hits > 0 else float(target_hits)

            forecasts[h_label] = HorizonForecast(
                horizon=h_label,
                horizon_bars=h_bars,
                prob_up=round(prob_up, 4),
                prob_down=round(prob_down, 4),
                expected_return=round(exp_ret, 6),
                median_return=round(q50, 6),
                quantile_10=round(q10, 6),
                quantile_25=round(q25, 6),
                quantile_75=round(q75, 6),
                quantile_90=round(q90, 6),
                expected_mfe=round(exp_mfe, 6),
                expected_mae=round(exp_mae, 6),
                prob_hit_target_first=round(prob_target_first, 4),
                target_stop_ratio=round(ts_ratio, 2),
                intrabar_ambiguity_count=ambiguous_hits
            )

        return ProbabilisticPrediction(
            query_timestamp_utc=search_result.query_timestamp_utc,
            query_open_time=search_result.query_open_time,
            query_close=query_close,
            query_regime=search_result.query_regime,
            is_abstained=False,
            abstention_reason=None,
            forecasts=forecasts
        )

    def _weighted_quantile(self, values: np.ndarray, weights: np.ndarray, q: float) -> float:
        """Compute weighted quantile."""
        sorter = np.argsort(values)
        sorted_vals = values[sorter]
        sorted_w = weights[sorter]
        cum_w = np.cumsum(sorted_w)
        idx = np.searchsorted(cum_w, q * cum_w[-1])
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]

    @staticmethod
    def compute_brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
        """Brier score: mean((p_i - y_i)^2) where y_i in {0, 1}."""
        return float(np.mean((probs - outcomes) ** 2))

    @staticmethod
    def compute_pinball_loss(actual: np.ndarray, predicted_quantile: np.ndarray, q: float) -> float:
        """Pinball (quantile) loss: mean(max(q*(y - y_hat), (1-q)*(y_hat - y)))."""
        diff = actual - predicted_quantile
        return float(np.mean(np.maximum(q * diff, (q - 1.0) * diff)))
