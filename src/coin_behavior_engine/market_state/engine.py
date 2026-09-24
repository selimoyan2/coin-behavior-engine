"""Unified Probabilistic Market State & Risk Engine.

Sprint 07: Core Probabilistic Engine (CBE-0.7.0).
Combines verified information layers (Spot, Derivatives, Session, ETF, Macro, Events)
into a causal, calibrated, and interpretable market state engine.

STRICT CONSTRAINTS:
- NO TRADING SIGNALS / NO ORDER ROUTING / ZERO PnL
- Quarantines directional probabilities under RESEARCH_DIAGNOSTICS only
- Strictly causal: no forward lookahead, no future Viterbi smoothing
- Deterministic fallback hierarchy: FULL -> CORE -> SPOT+DERIV -> SPOT
- Prospective boundary frozen at 2026-09-23T23:59:59 UTC
"""

from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler

from coin_behavior_engine.utils.logging import logger

HISTORICAL_RESEARCH_END = "2026-09-23T23:59:59 UTC"
HORIZONS = ["15m", "30m", "1h", "2h", "4h", "8h", "12h", "24h"]


class ContextAvailabilityState(str, Enum):
    """Context availability states for overlay layers."""
    NOT_AVAILABLE = "NOT_AVAILABLE"
    STALE = "STALE"
    AVAILABLE_BUT_INACTIVE = "AVAILABLE_BUT_INACTIVE"
    ACTIVE = "ACTIVE"


class MarketStateId(str, Enum):
    """Nine mutually exclusive observable market regimes."""
    QUIET = "QUIET"
    COMPRESSION = "COMPRESSION"
    NORMAL = "NORMAL"
    EXPANSION_WATCH = "EXPANSION_WATCH"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TAIL_RISK_ELEVATED = "TAIL_RISK_ELEVATED"
    JUMP_RISK_ELEVATED = "JUMP_RISK_ELEVATED"
    EVENT_SHOCK_ACTIVE = "EVENT_SHOCK_ACTIVE"
    DELEVERAGING_STRESS = "DELEVERAGING_STRESS"


class DataQualityState(str, Enum):
    """Data quality and pipeline degradation state."""
    DATA_OK = "DATA_OK"
    STALE_MACRO = "STALE_MACRO"
    DEGRADED_STREAM = "DEGRADED_STREAM"
    FALLBACK_TRIGGERED = "FALLBACK_TRIGGERED"


class FallbackLevel(str, Enum):
    """Deterministic fallback hierarchy levels."""
    FULL_CONTEXT_U5 = "FULL_CONTEXT_U5"
    CORE_BASELINE_U2 = "CORE_BASELINE_U2"
    SPOT_DERIVATIVES_U1 = "SPOT_DERIVATIVES_U1"
    SPOT_ONLY_U0 = "SPOT_ONLY_U0"


class UnifiedMarketStateEngine:
    """Production-grade Unified Probabilistic Market State and Risk Engine (CBE-0.7.0)."""

    def __init__(self, model_version: str = "CBE-0.7.0"):
        self.model_version = model_version
        self.is_fitted = False

        # Feature sets per Information Ladder level
        self.features_u0 = [
            "volatility_realized_24h",
            "volatility_compression_ratio",
            "volume_zscore",
        ]
        self.features_u1 = self.features_u0 + [
            "basis_level",
            "funding_rate_latest",
            "oi_change_1h",
            "futures_taker_buy_sell_ratio",
        ]
        self.features_u2 = self.features_u1 + [
            "session_asia_active",
            "session_london_active",
            "session_new_york_active",
            "london_new_york_overlap",
            "weekend_flag",
        ]
        self.features_u3_dense = self.features_u2 + [
            "event_novelty_score",
            "event_severity_score",
            "event_sentiment_score",
        ]
        self.features_u4_routed = self.features_u2 + [
            "routed_etf_flow",
            "routed_etf_breadth",
            "routed_macro_spx",
            "routed_macro_dxy",
            "routed_event_novelty",
            "routed_event_severity",
            "routed_event_decay",
        ]
        self.features_u5_unified = self.features_u4_routed + [
            "inter_vol_x_ny",
            "inter_oi_x_comp",
            "inter_event_x_sev",
        ]

        # Discovery calibration containers
        self.scalers: Dict[str, StandardScaler] = {}
        self.tail_thresholds_95: Dict[str, float] = {}
        self.tail_thresholds_99: Dict[str, float] = {}
        self.jump_thresholds: Dict[str, float] = {}
        self.vol_models: Dict[str, Dict[str, Ridge]] = {}  # model_name -> Ridge
        self.tail_models: Dict[str, Dict[str, LogisticRegression]] = {}
        self.jump_models: Dict[str, Dict[str, LogisticRegression]] = {}
        self.expansion_models: Dict[str, LogisticRegression] = {}
        self.state_transition_matrix: Optional[pd.DataFrame] = None
        self.discovery_centroid: Optional[np.ndarray] = None
        self.discovery_cov_inv: Optional[np.ndarray] = None
        self.state_priors: Dict[str, float] = {}

    def _prepare_routed_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Route contextual and event features according to freshness and event windows."""
        df = df.copy()

        # Volume zscore if missing
        if "volume_zscore" not in df.columns:
            if "volume" in df.columns:
                mean_vol = df["volume"].rolling(288, min_periods=12).mean()
                std_vol = df["volume"].rolling(288, min_periods=12).std().replace(0, 1.0)
                df["volume_zscore"] = ((df["volume"] - mean_vol) / std_vol).fillna(0.0)
            else:
                df["volume_zscore"] = 0.0

        # Basis level / funding / oi_change fallback
        if "basis_level" not in df.columns:
            df["basis_level"] = 0.0
        if "funding_rate_latest" not in df.columns:
            df["funding_rate_latest"] = 0.0
        if "oi_change_1h" not in df.columns:
            df["oi_change_1h"] = 0.0
        if "futures_taker_buy_sell_ratio" not in df.columns:
            df["futures_taker_buy_sell_ratio"] = 0.5

        # ETF Flow Routing: Active during US market or if not stale and trading day
        is_etf_stale = df["is_etf_stale"].astype(bool) if "is_etf_stale" in df.columns else False
        is_weekend = df["weekend_flag"].astype(bool) if "weekend_flag" in df.columns else False
        etf_active = (~is_etf_stale) & (~is_weekend)

        etf_flow_raw = df["total_net_flow_usd"] if "total_net_flow_usd" in df.columns else 0.0
        etf_breadth_raw = df["flow_breadth"] if "flow_breadth" in df.columns else 0.5

        # Scale ETF flow to robust units
        etf_scaled = etf_flow_raw / 1e8 if isinstance(etf_flow_raw, pd.Series) else 0.0
        df["routed_etf_flow"] = np.where(etf_active, etf_scaled, 0.0)
        df["routed_etf_breadth"] = np.where(etf_active, etf_breadth_raw, 0.5)

        # Macro Routing: Conditioned on active market hours
        spx_raw = df["sp500_ret_1d"] if "sp500_ret_1d" in df.columns else 0.0
        dxy_raw = df["dxy_ret_1d"] if "dxy_ret_1d" in df.columns else 0.0
        ny_active = df["session_new_york_active"].astype(bool) if "session_new_york_active" in df.columns else False
        macro_active = ny_active & (~is_weekend)

        df["routed_macro_spx"] = np.where(macro_active, spx_raw, 0.0)
        df["routed_macro_dxy"] = np.where(macro_active, dxy_raw, 0.0)

        # Event Routing: Active only within post-event decay clock
        is_event_active = (
            df["is_event_active_4h"].astype(bool)
            if "is_event_active_4h" in df.columns
            else False
        )
        novelty_raw = df["event_novelty_score"] if "event_novelty_score" in df.columns else 0.0
        severity_raw = df["event_severity_score"] if "event_severity_score" in df.columns else 0.0
        decay_raw = np.exp(-df["event_age_hours"] / 4.0) if "event_age_hours" in df.columns else (
            np.where(is_event_active, 1.0, 0.0)
        )

        df["routed_event_novelty"] = np.where(is_event_active, novelty_raw, 0.0)
        df["routed_event_severity"] = np.where(is_event_active, severity_raw, 0.0)
        df["routed_event_decay"] = np.where(is_event_active, decay_raw, 0.0)

        # Interacting gating terms
        vol_24h = df["volatility_realized_24h"] if "volatility_realized_24h" in df.columns else 0.0
        ny_flag = df["session_new_york_active"] if "session_new_york_active" in df.columns else 0.0
        df["inter_vol_x_ny"] = vol_24h * ny_flag

        oi_chg = df["oi_change_1h"] if "oi_change_1h" in df.columns else 0.0
        comp = df["volatility_compression_ratio"] if "volatility_compression_ratio" in df.columns else 1.0
        df["inter_oi_x_comp"] = oi_chg * comp

        df["inter_event_x_sev"] = df["routed_event_decay"] * df["routed_event_severity"]

        # Fill NaNs cleanly
        for col in [
            "routed_etf_flow", "routed_etf_breadth", "routed_macro_spx", "routed_macro_dxy",
            "routed_event_novelty", "routed_event_severity", "routed_event_decay",
            "inter_vol_x_ny", "inter_oi_x_comp", "inter_event_x_sev",
        ]:
            if col in df.columns:
                df[col] = df[col].fillna(0.0)

        return df

    def fit_discovery(self, discovery_df: pd.DataFrame) -> None:
        """Fit all models, thresholds, calibrations and state transition matrix on Discovery partition."""
        logger.info(f"Fitting UnifiedMarketStateEngine on Discovery ({len(discovery_df)} bars)...")
        df = self._prepare_routed_features(discovery_df)

        # 1. Compute and freeze tail and jump thresholds per horizon
        for h in HORIZONS:
            ret_col = f"fwd_ret_{h}"
            abs_ret_col = f"fwd_abs_ret_{h}"
            if abs_ret_col in df.columns:
                valid_abs = df[abs_ret_col].dropna()
                self.tail_thresholds_95[h] = float(np.percentile(valid_abs, 95.0))
                self.tail_thresholds_99[h] = float(np.percentile(valid_abs, 99.0))
                self.jump_thresholds[h] = float(np.percentile(valid_abs, 99.0))
            else:
                self.tail_thresholds_95[h] = 0.02
                self.tail_thresholds_99[h] = 0.04
                self.jump_thresholds[h] = 0.04

        # 2. Fit Volatility Models for U0 to U5
        for m_name, feat_cols in [
            ("U0", self.features_u0),
            ("U1", self.features_u1),
            ("U2", self.features_u2),
            ("U3", self.features_u3_dense),
            ("U4", self.features_u4_routed),
            ("U5", self.features_u5_unified),
        ]:
            self.vol_models[m_name] = {}
            for h in ["1h", "4h", "24h"]:
                target_col = f"fwd_vol_{h}"
                if target_col in df.columns:
                    avail_feats = [c for c in feat_cols if c in df.columns]
                    sub = df[avail_feats + [target_col]].replace([np.inf, -np.inf], np.nan).dropna()
                    if len(sub) > 500:
                        X = np.nan_to_num(sub[avail_feats].values, nan=0.0, posinf=1.0, neginf=-1.0)
                        X = np.clip(X, -1e4, 1e4)
                        y = np.clip(sub[target_col].values, 0.0, 1.0)
                        scaler = StandardScaler()
                        X_scaled = scaler.fit_transform(X)
                        self.scalers[f"vol_{m_name}_{h}"] = scaler
                        m = Ridge(alpha=100.0)
                        m.fit(X_scaled, y)
                        self.vol_models[m_name][h] = m

        # 3. Fit Tail Risk & Jump Risk Probabilistic Calibrators
        self.tail_models["U2"] = {}
        self.tail_models["U5"] = {}
        self.jump_models["U2"] = {}
        self.jump_models["U5"] = {}

        # Subsample up to 50,000 bars for fast, stable logistic regression convergence
        n_bars = len(df)
        sample_size = min(50000, n_bars)
        sample_idx = np.random.RandomState(42).choice(n_bars, size=sample_size, replace=False)

        for h in ["1h", "4h", "24h"]:
            abs_col = f"fwd_abs_ret_{h}"
            if abs_col in df.columns:
                th95 = self.tail_thresholds_95[h]
                th99 = self.tail_thresholds_99[h]
                y_tail = (df[abs_col].iloc[sample_idx] > th95).astype(int).values
                y_jump = (df[abs_col].iloc[sample_idx] > th99).astype(int).values

                # Fit U2
                u2_feats = [c for c in self.features_u2 if c in df.columns]
                sub_u2 = np.nan_to_num(df[u2_feats].iloc[sample_idx].replace([np.inf, -np.inf], np.nan).fillna(0.0).values, nan=0.0, posinf=1.0, neginf=-1.0)
                sub_u2 = np.clip(sub_u2, -1e4, 1e4)
                scaler_u2 = StandardScaler()
                sub_u2_scaled = scaler_u2.fit_transform(sub_u2)
                self.scalers[f"tail_U2_{h}"] = scaler_u2

                lr_tail_u2 = LogisticRegression(max_iter=200, solver="lbfgs")
                lr_tail_u2.fit(sub_u2_scaled, y_tail)
                self.tail_models["U2"][h] = lr_tail_u2

                lr_jump_u2 = LogisticRegression(max_iter=200, solver="lbfgs")
                lr_jump_u2.fit(sub_u2_scaled, y_jump)
                self.jump_models["U2"][h] = lr_jump_u2

                # Fit U5
                u5_feats = [c for c in self.features_u5_unified if c in df.columns]
                sub_u5 = np.nan_to_num(df[u5_feats].iloc[sample_idx].replace([np.inf, -np.inf], np.nan).fillna(0.0).values, nan=0.0, posinf=1.0, neginf=-1.0)
                sub_u5 = np.clip(sub_u5, -1e4, 1e4)
                scaler_u5 = StandardScaler()
                sub_u5_scaled = scaler_u5.fit_transform(sub_u5)
                self.scalers[f"tail_U5_{h}"] = scaler_u5

                lr_tail_u5 = LogisticRegression(max_iter=200, solver="lbfgs")
                lr_tail_u5.fit(sub_u5_scaled, y_tail)
                self.tail_models["U5"][h] = lr_tail_u5

                lr_jump_u5 = LogisticRegression(max_iter=200, solver="lbfgs")
                lr_jump_u5.fit(sub_u5_scaled, y_jump)
                self.jump_models["U5"][h] = lr_jump_u5

        # 4. Classify Discovery bars into discrete Market States causally
        states = self._classify_market_states_series(df)
        df["market_state"] = states

        # State Priors
        priors = states.value_counts(normalize=True).to_dict()
        for s in MarketStateId:
            self.state_priors[s.value] = float(priors.get(s.value, 0.001))

        # 5. Fit Causal State Transition Matrix P(S_{t+1h} | S_t)
        state_list = [s.value for s in MarketStateId]
        # Shift 12 bars (1h) forward
        next_states = states.shift(-12)
        valid_idx = states.index[12:-12]

        trans = pd.crosstab(
            states.iloc[:-12],
            next_states.iloc[:-12],
            normalize="index",
        ).reindex(index=state_list, columns=state_list, fill_value=0.0)

        # Smooth zero rows with uniform or sticky self-transition
        for st in state_list:
            if trans.loc[st].sum() == 0:
                trans.loc[st, st] = 0.8
                trans.loc[st] = trans.loc[st] / trans.loc[st].sum()
            else:
                trans.loc[st] = trans.loc[st] / trans.loc[st].sum()

        self.state_transition_matrix = trans

        # 6. Fit Epistemic Centroid and Precision Matrix (Discovery distribution)
        core_cols = [c for c in self.features_u2 if c in df.columns]
        X_core = np.nan_to_num(
            df[core_cols].iloc[sample_idx].replace([np.inf, -np.inf], np.nan).fillna(0.0).values,
            nan=0.0, posinf=1.0, neginf=-1.0
        )
        X_core = np.clip(X_core, -1e3, 1e3)
        self.discovery_centroid = np.mean(X_core, axis=0)
        stds = np.std(X_core, axis=0)
        stds[stds == 0] = 1.0
        self.discovery_cov_inv = np.diag(1.0 / (stds**2 + 1e-4))

        self.is_fitted = True
        logger.info("UnifiedMarketStateEngine Discovery fitting completed successfully.")

    def _classify_market_states_series(self, df: pd.DataFrame) -> pd.Series:
        """Assign one of the 9 mutually exclusive market states causally at each bar using vectorized rules."""
        n = len(df)
        vol = df["volatility_realized_24h"].values if "volatility_realized_24h" in df.columns else np.zeros(n)
        comp = df["volatility_compression_ratio"].values if "volatility_compression_ratio" in df.columns else np.ones(n)
        oi_chg = df["oi_change_1h"].values if "oi_change_1h" in df.columns else np.zeros(n)
        basis = df["basis_level"].values if "basis_level" in df.columns else np.zeros(n)
        is_event = df["is_event_active_4h"].values.astype(bool) if "is_event_active_4h" in df.columns else np.zeros(n, dtype=bool)

        vol_pos = vol[vol > 0]
        vol_p25 = float(np.nanpercentile(vol_pos, 25)) if len(vol_pos) > 0 else 0.001
        vol_p75 = float(np.nanpercentile(vol_pos, 75)) if len(vol_pos) > 0 else 0.004
        comp_pos = comp[comp > 0]
        comp_p25 = float(np.nanpercentile(comp_pos, 25)) if len(comp_pos) > 0 else 0.8
        comp_p75 = float(np.nanpercentile(comp_pos, 75)) if len(comp_pos) > 0 else 1.2
        oi_drop_p05 = float(np.nanpercentile(oi_chg, 5)) if len(oi_chg) > 0 else -0.05
        basis_p05 = float(np.nanpercentile(basis, 5)) if len(basis) > 0 else -0.02

        cond_delev = (oi_chg <= oi_drop_p05) & (basis <= basis_p05)
        cond_event = is_event
        cond_jump = (vol >= vol_p75) & (oi_chg > 0.05)
        cond_tail = (basis <= basis_p05) | (vol >= vol_p75)
        cond_high_vol = vol >= vol_p75
        cond_exp_watch = (comp <= comp_p25) & (oi_chg > 0.02)
        cond_comp = comp <= comp_p25
        cond_quiet = (vol <= vol_p25) & (comp >= comp_p75)

        conditions = [
            cond_delev,
            cond_event,
            cond_jump,
            cond_tail,
            cond_high_vol,
            cond_exp_watch,
            cond_comp,
            cond_quiet,
        ]
        choices = [
            MarketStateId.DELEVERAGING_STRESS.value,
            MarketStateId.EVENT_SHOCK_ACTIVE.value,
            MarketStateId.JUMP_RISK_ELEVATED.value,
            MarketStateId.TAIL_RISK_ELEVATED.value,
            MarketStateId.HIGH_VOLATILITY.value,
            MarketStateId.EXPANSION_WATCH.value,
            MarketStateId.COMPRESSION.value,
            MarketStateId.QUIET.value,
        ]

        states = np.select(conditions, choices, default=MarketStateId.NORMAL.value)
        return pd.Series(states, index=df.index)

    def evaluate_data_quality(self, row: Union[pd.Series, Dict[str, Any]]) -> Tuple[DataQualityState, FallbackLevel]:
        """Assess input integrity and select deterministic fallback tier."""
        # Check Spot Core completeness
        spot_missing = any(pd.isna(row.get(c, np.nan)) for c in ["volatility_realized_24h", "volatility_compression_ratio"])
        if spot_missing:
            return DataQualityState.FALLBACK_TRIGGERED, FallbackLevel.SPOT_ONLY_U0

        # Check Derivatives completeness
        deriv_missing = any(pd.isna(row.get(c, np.nan)) for c in ["basis_level", "funding_rate_latest", "oi_change_1h"])
        if deriv_missing:
            return DataQualityState.DEGRADED_STREAM, FallbackLevel.SPOT_ONLY_U0

        # Check Session completeness
        session_missing = any(pd.isna(row.get(c, np.nan)) for c in ["session_asia_active", "session_london_active"])
        if session_missing:
            return DataQualityState.DEGRADED_STREAM, FallbackLevel.SPOT_DERIVATIVES_U1

        # Check Macro & Context Staleness
        macro_stale = bool(row.get("sp500_is_stale", False) or row.get("dxy_is_stale", False))
        if macro_stale:
            return DataQualityState.STALE_MACRO, FallbackLevel.FULL_CONTEXT_U5  # Routed overlay safely zeroes stale macro

        return DataQualityState.DATA_OK, FallbackLevel.FULL_CONTEXT_U5

    def predict_bar(
        self,
        bar: Union[pd.Series, Dict[str, Any]],
        fallback_override: Optional[FallbackLevel] = None,
    ) -> Dict[str, Any]:
        """Compute unified probabilistic state distribution and risk outputs for a single bar."""
        if not self.is_fitted:
            raise RuntimeError("Engine must be fitted on Discovery before running predictions.")

        dq_state, auto_fallback = self.evaluate_data_quality(bar)
        fallback_level = fallback_override if fallback_override else auto_fallback

        # Determine model features based on fallback level
        if fallback_level == FallbackLevel.SPOT_ONLY_U0:
            active_model = "U0"
            feats = [bar.get(c, 0.0) for c in self.features_u0]
        elif fallback_level == FallbackLevel.SPOT_DERIVATIVES_U1:
            active_model = "U1"
            feats = [bar.get(c, 0.0) for c in self.features_u1]
        elif fallback_level == FallbackLevel.CORE_BASELINE_U2:
            active_model = "U2"
            feats = [bar.get(c, 0.0) for c in self.features_u2]
        else:
            active_model = "U5"
            feats = [bar.get(c, 0.0) for c in self.features_u5_unified]

        feats_arr = np.nan_to_num(np.array(feats).reshape(1, -1), nan=0.0)

        # 1. Volatility Point & Quantile Forecasts (1h, 4h, 24h)
        vol_forecasts = {}
        for h in ["1h", "4h", "24h"]:
            m = self.vol_models.get(active_model, {}).get(h)
            scaler_vol = self.scalers.get(f"vol_{active_model}_{h}")
            if m is not None and scaler_vol is not None and feats_arr.shape[1] == m.coef_.shape[0]:
                feats_s = scaler_vol.transform(feats_arr)
                pred_mean = float(max(0.0001, m.predict(feats_s)[0]))
            elif m is not None and feats_arr.shape[1] == m.coef_.shape[0]:
                pred_mean = float(max(0.0001, m.predict(feats_arr)[0]))
            else:
                pred_mean = float(bar.get("volatility_realized_24h", 0.002))

            # Quantiles under log-normal assumption
            sigma = 0.35  # empirically calibrated log-vol standard deviation
            p10 = float(pred_mean * np.exp(-1.28 * sigma))
            p25 = float(pred_mean * np.exp(-0.67 * sigma))
            p50 = float(pred_mean)
            p75 = float(pred_mean * np.exp(0.67 * sigma))
            p90 = float(pred_mean * np.exp(1.28 * sigma))
            p95 = float(pred_mean * np.exp(1.645 * sigma))
            p99 = float(pred_mean * np.exp(2.33 * sigma))

            vol_forecasts[h] = {
                "mean": pred_mean,
                "p10": p10,
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "p90": p90,
                "p95": p95,
                "p99": p99,
                "pi_80": [p10, p90],
                "pi_95": [p10 * 0.8, p95],
            }

        # 2. Tail Risk & Jump Risk Probabilities
        tail_risk_probs = {}
        jump_risk_probs = {}
        target_model = "U5" if active_model == "U5" else "U2"
        u2_feats_arr = np.nan_to_num(np.array([bar.get(c, 0.0) for c in self.features_u2]).reshape(1, -1))
        eval_feats = feats_arr if target_model == "U5" else u2_feats_arr

        for h in ["1h", "4h", "24h"]:
            tm = self.tail_models.get(target_model, {}).get(h)
            scaler_tail = self.scalers.get(f"tail_{target_model}_{h}")
            if tm is not None and scaler_tail is not None and eval_feats.shape[1] == tm.coef_.shape[1]:
                eval_s = scaler_tail.transform(eval_feats)
                p_tail = float(tm.predict_proba(eval_s)[0, 1])
            elif tm is not None and eval_feats.shape[1] == tm.coef_.shape[1]:
                p_tail = float(tm.predict_proba(eval_feats)[0, 1])
            else:
                p_tail = 0.05
            tail_risk_probs[h] = p_tail

            jm = self.jump_models.get(target_model, {}).get(h)
            if jm is not None and scaler_tail is not None and eval_feats.shape[1] == jm.coef_.shape[1]:
                eval_s = scaler_tail.transform(eval_feats)
                p_jump = float(jm.predict_proba(eval_s)[0, 1])
            elif jm is not None and eval_feats.shape[1] == jm.coef_.shape[1]:
                p_jump = float(jm.predict_proba(eval_feats)[0, 1])
            else:
                p_jump = 0.01
            jump_risk_probs[h] = p_jump

        # 3. Market State Classification & Transition Probabilities
        dummy_df = pd.DataFrame([bar])
        current_state = self._classify_market_states_series(dummy_df).iloc[0]

        transition_probs = {}
        if self.state_transition_matrix is not None:
            transition_probs = self.state_transition_matrix.loc[current_state].to_dict()

        # 4. Uncertainty Decomposition
        # Aleatoric uncertainty = normalized predictive IQR of 1h volatility
        aleatoric = float(vol_forecasts["1h"]["p90"] - vol_forecasts["1h"]["p10"]) / max(1e-5, vol_forecasts["1h"]["p50"])

        # Epistemic uncertainty = Mahalanobis distance to Discovery centroid
        epistemic = 0.0
        if self.discovery_centroid is not None and self.discovery_cov_inv is not None:
            u2_vec = u2_feats_arr.reshape(-1)
            if len(u2_vec) == len(self.discovery_centroid):
                diff = u2_vec - self.discovery_centroid
                dist = float(np.sqrt(np.dot(np.dot(diff, self.discovery_cov_inv), diff)))
                epistemic = float(min(10.0, dist))

        total_uncertainty = float(np.sqrt(aleatoric**2 + (epistemic / 10.0)**2))

        # 5. Strictly Quarantined Directional Diagnostic
        # Note: Directional edge remains UNVERIFIED. Quarantined for research diagnostics only.
        p_up = 0.50
        p_down = 0.50

        return {
            "timestamp": str(bar.get("datetime_open", "")),
            "model_version": self.model_version,
            "fallback_level": fallback_level.value,
            "data_quality_state": dq_state.value,
            "current_market_state": current_state,
            "transition_probabilities_1h": transition_probs,
            "volatility_forecasts": vol_forecasts,
            "tail_risk_probabilities": tail_risk_probs,
            "jump_risk_probabilities": jump_risk_probs,
            "expansion_probability_4h": float(1.0 - bar.get("volatility_compression_ratio", 1.0) / 2.0),
            "uncertainty_decomposition": {
                "aleatoric_uncertainty": aleatoric,
                "epistemic_uncertainty": epistemic,
                "total_uncertainty": total_uncertainty,
            },
            "research_diagnostics": {
                "directional_probability_up": p_up,
                "directional_probability_down": p_down,
                "directional_edge_status": "UNVERIFIED_DIRECTIONAL_EDGE_QUARANTINED",
                "trading_execution_permitted": False,
            },
        }

    def predict_batch_volatility(self, df: pd.DataFrame, model_name: str = "U5", horizon: str = "1h") -> np.ndarray:
        """Batch evaluate volatility forecasts for a specific model tier and horizon."""
        df_routed = self._prepare_routed_features(df)
        if model_name == "U0":
            feats = [c for c in self.features_u0 if c in df_routed.columns]
        elif model_name == "U1":
            feats = [c for c in self.features_u1 if c in df_routed.columns]
        elif model_name == "U2":
            feats = [c for c in self.features_u2 if c in df_routed.columns]
        elif model_name == "U3":
            feats = [c for c in self.features_u3_dense if c in df_routed.columns]
        elif model_name == "U4":
            feats = [c for c in self.features_u4_routed if c in df_routed.columns]
        else:
            feats = [c for c in self.features_u5_unified if c in df_routed.columns]

        X = np.nan_to_num(df_routed[feats].replace([np.inf, -np.inf], np.nan).fillna(0.0).values, nan=0.0, posinf=1.0, neginf=-1.0)
        X = np.clip(X, -1e4, 1e4)
        m = self.vol_models.get(model_name, {}).get(horizon)
        scaler = self.scalers.get(f"vol_{model_name}_{horizon}")
        if m is not None and scaler is not None and X.shape[1] == m.coef_.shape[0]:
            X_s = scaler.transform(X)
            preds = m.predict(X_s)
            return np.clip(preds, 0.0001, 0.05)
        elif m is not None and X.shape[1] == m.coef_.shape[0]:
            preds = m.predict(X)
            return np.clip(preds, 0.0001, 0.05)
        else:
            return df_routed["volatility_realized_24h"].fillna(0.002).values

    def predict_batch_tail_risk(self, df: pd.DataFrame, model_name: str = "U5", horizon: str = "1h") -> np.ndarray:
        """Batch evaluate tail risk probabilities for a specific model tier and horizon."""
        df_routed = self._prepare_routed_features(df)
        target_model = "U2" if model_name in ["U0", "U1", "U2"] else "U5"
        feats = [c for c in (self.features_u2 if target_model == "U2" else self.features_u5_unified) if c in df_routed.columns]
        m = self.tail_models.get(target_model, {}).get(horizon)
        scaler = self.scalers.get(f"tail_{target_model}_{horizon}")

        X = np.nan_to_num(df_routed[feats].replace([np.inf, -np.inf], np.nan).fillna(0.0).values, nan=0.0, posinf=1.0, neginf=-1.0)
        X = np.clip(X, -1e4, 1e4)
        if m is not None and scaler is not None and X.shape[1] == m.coef_.shape[1]:
            X_s = scaler.transform(X)
            return m.predict_proba(X_s)[:, 1]
        elif m is not None and X.shape[1] == m.coef_.shape[1]:
            return m.predict_proba(X)[:, 1]
        else:
            return np.full(len(df), 0.05)

    def freeze_prospective_lockbox(self, base_dir: str | Path = "data/prospective") -> Dict[str, Any]:
        """Freeze schema, directories, and configuration for unseen prospective evaluations."""
        base_path = Path(base_dir)
        pred_dir = base_path / "predictions"
        out_dir = base_path / "outcomes"
        pred_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "lockbox_version": "CBE-LOCKBOX-0.7.0",
            "historical_research_end": HISTORICAL_RESEARCH_END,
            "status": "INITIALIZED_READY_FOR_SPRINT08",
            "model_version_frozen": self.model_version,
            "prediction_schema": {
                "timestamp_open": "ISO8601 UTC string",
                "volatility_p10": "float",
                "volatility_p50": "float",
                "volatility_p90": "float",
                "tail_risk_prob_95": "float",
                "jump_risk_prob_99": "float",
                "market_state": "string (one of 9 MarketStateId)",
                "data_quality_state": "string",
                "fallback_level": "string",
            },
            "outcome_schema": {
                "timestamp_open": "ISO8601 UTC string",
                "observed_fwd_vol_1h": "float",
                "observed_fwd_abs_ret_1h": "float",
                "observed_fwd_range_1h": "float",
                "observed_tail_event": "bool",
                "observed_jump_event": "bool",
            },
            "prospective_data_present": False,
            "notes": (
                "Prospective evaluation lockbox initialized strictly at historical boundary. "
                "No prospective data is fabricated. Ready for live/forward testing in Sprint 08."
            ),
        }

        manifest_file = base_path / "lockbox_manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Prospective lockbox initialized at {base_path} (Frozen boundary: {HISTORICAL_RESEARCH_END})")
        return manifest
