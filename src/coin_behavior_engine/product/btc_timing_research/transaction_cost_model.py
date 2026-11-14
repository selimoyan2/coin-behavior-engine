"""Historical Transaction Cost Model (Module 29.4).

Provides documented, transparent transaction cost assumptions for historical BTC/USDT paper simulations:
1. Exchange commissions (maker / taker fees).
2. Bid-ask spread assumptions.
3. Execution slippage estimates.
4. Three canonical cost tiers: LOW_COST, BASE_COST, HIGH_COST.
5. Cost sensitivity auditing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TransactionCostProfile:
    """Specification of transaction cost parameters."""
    profile_id: str
    name: str
    maker_fee_pct: float
    taker_fee_pct: float
    bid_ask_spread_pct: float
    slippage_pct: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


CANONICAL_COST_PROFILES: Dict[str, TransactionCostProfile] = {
    "LOW_COST": TransactionCostProfile(
        profile_id="LOW_COST",
        name="Low Cost Scenario (VIP / High-Tier)",
        maker_fee_pct=0.0002,      # 0.02% (2 bps)
        taker_fee_pct=0.0005,      # 0.05% (5 bps)
        bid_ask_spread_pct=0.0002, # 0.02% (2 bps)
        slippage_pct=0.0001,       # 0.01% (1 bp)
        description="Low-fee environment simulating institutional or high-tier fee schedule on liquid BTC/USDT.",
    ),
    "BASE_COST": TransactionCostProfile(
        profile_id="BASE_COST",
        name="Base Cost Scenario (Standard Retail)",
        maker_fee_pct=0.0010,      # 0.10% (10 bps)
        taker_fee_pct=0.0010,      # 0.10% (10 bps)
        bid_ask_spread_pct=0.0005, # 0.05% (5 bps)
        slippage_pct=0.0005,       # 0.05% (5 bps)
        description="Standard baseline environment reflecting standard exchange fees and realistic retail execution frictions.",
    ),
    "HIGH_COST": TransactionCostProfile(
        profile_id="HIGH_COST",
        name="High Cost Scenario (Adverse Execution / Frictions)",
        maker_fee_pct=0.0020,      # 0.20% (20 bps)
        taker_fee_pct=0.0020,      # 0.20% (20 bps)
        bid_ask_spread_pct=0.0010, # 0.10% (10 bps)
        slippage_pct=0.0015,       # 0.15% (15 bps)
        description="Conservative stress scenario reflecting wide spreads, market volatility, and elevated slippage.",
    ),
}


@dataclass(frozen=True)
class TradeCostBreakdown:
    """Itemized costs for a single historical trade."""
    trade_value_usdt: float
    nominal_price: float
    effective_execution_price: float
    fee_usdt: float
    spread_cost_usdt: float
    slippage_cost_usdt: float
    total_transaction_cost_usdt: float
    cost_drag_bps: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TransactionCostEngine:
    """Applies transaction cost models to historical simulated trades."""

    def __init__(self, profile_id: str = "BASE_COST"):
        if profile_id not in CANONICAL_COST_PROFILES:
            raise ValueError(f"Unknown cost profile '{profile_id}'. Allowed: {list(CANONICAL_COST_PROFILES.keys())}")
        self.profile = CANONICAL_COST_PROFILES[profile_id]

    def compute_costs(
        self,
        nominal_trade_value_usdt: float,
        nominal_price: float,
        is_buy: bool,
    ) -> TradeCostBreakdown:
        """Calculate fees, spread drag, and slippage for a given trade.

        For Buy orders:
        - Buyer pays half the bid-ask spread above midpoint.
        - Buyer experiences adverse slippage (execution price higher).
        - Effective execution price = nominal_price * (1 + spread/2 + slippage).

        For Sell orders:
        - Seller pays half the bid-ask spread below midpoint.
        - Seller experiences adverse slippage (execution price lower).
        - Effective execution price = nominal_price * (1 - spread/2 - slippage).
        """
        val = abs(float(nominal_trade_value_usdt))
        price = float(nominal_price)
        half_spread = self.profile.bid_ask_spread_pct / 2.0
        slippage = self.profile.slippage_pct

        if is_buy:
            effective_price = price * (1.0 + half_spread + slippage)
        else:
            effective_price = price * (1.0 - half_spread - slippage)

        fee = val * self.profile.taker_fee_pct
        spread_cost = val * half_spread
        slippage_cost = val * slippage
        total_cost = fee + spread_cost + slippage_cost

        cost_drag_bps = (total_cost / max(val, 1e-6)) * 10000.0

        return TradeCostBreakdown(
            trade_value_usdt=round(val, 4),
            nominal_price=round(price, 4),
            effective_execution_price=round(effective_price, 4),
            fee_usdt=round(fee, 4),
            spread_cost_usdt=round(spread_cost, 4),
            slippage_cost_usdt=round(slippage_cost, 4),
            total_transaction_cost_usdt=round(total_cost, 4),
            cost_drag_bps=round(cost_drag_bps, 2),
        )
