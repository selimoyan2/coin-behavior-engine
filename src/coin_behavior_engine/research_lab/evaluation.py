"""Strategy comparative evaluation and benchmark analysis engine.

Sprint 11.03: Market Behavior Research Lab.
Evaluates Strategy A (Technical Only), Strategy B (Context Aware), and Strategy C (Risk Controlled)
against Buy & Hold and Cash benchmarks under identical execution conditions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    DecisionMode,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    ProbabilisticPrediction,
    ResearchDecision,
    SimulationRunResult,
)
from coin_behavior_engine.research_lab.decision_engine import ResearchDecisionEngine
from coin_behavior_engine.research_lab.pattern_engine import BehavioralPatternEngine
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine
from coin_behavior_engine.research_lab.risk_engine import RiskEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator


class StrategyEvaluator:
    """Orchestrates multi-strategy backtesting and comparison across shared market data."""

    def __init__(self, config: Optional[ResearchLabConfig] = None):
        self.config = config or ResearchLabConfig()
        self.risk_engine = RiskEngine(self.config)
        self.decision_engine = ResearchDecisionEngine(self.risk_engine)
        self.simulator = HistoricalPaperSimulator(self.config)

    def run_strategy_comparison(
        self,
        candles: List[CandleData],
        features: List[MarketBehaviorFeatures],
        events: Optional[List[EventIntelligenceRecord]] = None,
    ) -> Dict[str, SimulationRunResult]:
        """Run all 3 strategies and return simulation results for each."""
        strategies = {
            "Strategy_A_Technical_Only": DecisionMode.TECHNICAL_ONLY_RESEARCH,
            "Strategy_B_Context_Aware": DecisionMode.CONTEXT_AWARE_RESEARCH,
            "Strategy_C_Risk_Controlled": DecisionMode.RISK_CONTROLLED_RESEARCH,
        }

        results: Dict[str, SimulationRunResult] = {}

        for strat_name, mode in strategies.items():
            decisions: List[ResearchDecision] = []
            
            for i in range(len(candles)):
                feat = features[i]
                c = candles[i]

                # Filter observable events up to current bar timestamp
                obs_events = []
                if events and mode == DecisionMode.CONTEXT_AWARE_RESEARCH:
                    obs_events = [
                        e for e in events
                        if e.first_observed_at_utc <= c.datetime_open_utc
                    ]

                # Active patterns
                patterns = BehavioralPatternEngine.match_patterns_at_index(
                    candles, features, i, observable_events=obs_events
                )

                # Probabilistic prediction
                pred = ProbabilityEngine.generate_prediction(
                    features=feat,
                    active_patterns=patterns,
                    observable_events=obs_events if obs_events else None,
                )

                # Generate decision
                dec = self.decision_engine.evaluate_decision(
                    features=feat,
                    prediction=pred,
                    active_patterns=patterns,
                    strategy_mode=mode,
                    observable_events=obs_events if obs_events else None,
                    current_capital=self.config.initial_capital_usdt,
                )
                decisions.append(dec)

            # Run simulation
            sim_res = self.simulator.simulate(
                candles=candles,
                decisions=decisions,
                strategy_name=strat_name,
            )
            results[strat_name] = sim_res

        return results

    @classmethod
    def generate_comparison_table(
        cls,
        results: Dict[str, SimulationRunResult],
    ) -> pd.DataFrame:
        """Create structured comparison DataFrame including benchmarks."""
        rows = []
        bnh_ret = 0.0
        for name, res in results.items():
            bnh_ret = res.baseline_buy_and_hold_return_pct
            rows.append({
                "Strategy": name,
                "Return (%)": res.return_pct,
                "Net PnL ($)": res.total_net_pnl,
                "Max Drawdown (%)": res.max_drawdown_pct,
                "Win Rate (%)": round(res.win_rate * 100.0, 1),
                "Profit Factor": res.profit_factor,
                "Expectancy ($)": res.expectancy,
                "Trades": res.total_trades,
                "Total Fees ($)": res.total_fees,
                "Sharpe": res.sharpe_ratio,
            })

        # Add Buy & Hold baseline
        first_res = next(iter(results.values()))
        init_cap = first_res.initial_capital
        bnh_pnl = round(init_cap * (bnh_ret / 100.0), 2)
        rows.append({
            "Strategy": "Benchmark_Buy_and_Hold",
            "Return (%)": bnh_ret,
            "Net PnL ($)": bnh_pnl,
            "Max Drawdown (%)": 0.0,  # Computed from price path if needed
            "Win Rate (%)": 0.0,
            "Profit Factor": 0.0,
            "Expectancy ($)": 0.0,
            "Trades": 1,
            "Total Fees ($)": round(init_cap * 0.001, 2),
            "Sharpe": 0.0,
        })

        # Add Cash baseline
        rows.append({
            "Strategy": "Benchmark_Cash",
            "Return (%)": 0.0,
            "Net PnL ($)": 0.0,
            "Max Drawdown (%)": 0.0,
            "Win Rate (%)": 0.0,
            "Profit Factor": 0.0,
            "Expectancy ($)": 0.0,
            "Trades": 0,
            "Total Fees ($)": 0.0,
            "Sharpe": 0.0,
        })

        df = pd.DataFrame(rows)
        return df

    @classmethod
    def export_comparison_csv(
        cls,
        comparison_df: pd.DataFrame,
        output_csv: Path,
    ) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        comparison_df.to_csv(output_csv, index=False)
