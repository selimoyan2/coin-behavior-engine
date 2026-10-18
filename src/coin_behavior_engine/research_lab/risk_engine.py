"""Dynamic risk management, position sizing, and volatility-adaptive stops.

Sprint 11.03: Market Behavior Research Lab.
Calculates volatility-adjusted stop-loss, take-profit, and max capital exposure
without lookahead.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.contracts import MarketBehaviorFeatures


class RiskEngine:
    """Manages risk constraints and order sizing parameters for historical paper simulation."""

    def __init__(self, config: Optional[ResearchLabConfig] = None):
        self.config = config or ResearchLabConfig()

    def calculate_trade_parameters(
        self,
        current_price: float,
        features: MarketBehaviorFeatures,
        current_capital: float,
        risk_mode: str = "STANDARD",  # "STANDARD" or "STRICT"
    ) -> Tuple[float, float, float, float]:
        """Returns: (position_size_usd, quantity_coin, stop_loss_price, take_profit_price)."""
        if current_price <= 0 or current_capital <= 0:
            return 0.0, 0.0, 0.0, 0.0

        atr = features.atr_14 if features.atr_14 > 0 else (current_price * 0.01)
        
        # Risk multipliers
        if risk_mode == "STRICT":
            sl_mult = 1.2
            tp_mult = 2.4
            max_alloc_pct = self.config.max_position_size_pct * 0.75  # e.g., 18.75%
            risk_pct = self.config.risk_per_trade_pct * 0.75  # 1.5%
        else:
            sl_mult = self.config.default_stop_loss_atr_mult
            tp_mult = self.config.default_take_profit_atr_mult
            max_alloc_pct = self.config.max_position_size_pct
            risk_pct = self.config.risk_per_trade_pct

        stop_loss_price = round(max(0.01, current_price - (atr * sl_mult)), 2)
        take_profit_price = round(current_price + (atr * tp_mult), 2)

        stop_distance = current_price - stop_loss_price
        stop_dist_pct = (stop_distance / current_price) if current_price > 0 else 0.02
        stop_dist_pct = max(0.005, stop_dist_pct)  # Minimum 0.5% stop distance

        # Capital at risk sizing
        risk_capital = current_capital * risk_pct
        desired_size_by_risk = risk_capital / stop_dist_pct
        max_allowed_size = current_capital * max_alloc_pct

        final_size_usd = round(min(desired_size_by_risk, max_allowed_size, current_capital), 2)
        quantity = round(final_size_usd / current_price, 6)

        return final_size_usd, quantity, stop_loss_price, take_profit_price
