# Coin Behavior Engine

> **Sprint 01: BTC Core Research Foundation**  
> **Mode:** Research-first / Data-first / No trading execution

## Overview

The **Coin Behavior Engine** is an institutional-grade research platform engineered to analyze cryptocurrency market microstructure, discover empirical behavioral patterns, and evaluate probabilistic market states without hardcoded trading heuristics or look-ahead bias.

Sprint 01 establishes the foundational data, validation, feature engineering, adaptive anomaly scoring, and market regime infrastructure for `BTCUSDT` over the 2026 research period.

## Critical Research Principles

1. **Data First:** Hypotheses are tested against data; rules are not arbitrarily imposed.
2. **No Look-Ahead Bias / No Future Leakage:** Feature pipelines only access information available at timestamp $T$.
3. **No Hardcoded Trading Rules:** No arbitrary assumptions such as "RSI < 30 means buy" or "3% move is big".
4. **Reproducible Results:** Pure functional transforms with explicit random seeds and parameter provenance.
5. **UTC Time Standard:** Microsecond/millisecond UTC awareness across all timestamps.
6. **Raw Immutability:** Ingested source files are strictly immutable and resumable.
7. **Rebuildable Derived Datasets:** Canonical normalized candles and higher timeframes are 100% rebuildable from raw data.
8. **Explainable Events:** Every candidate market anomaly is mapped to quantifiable statistical characteristics.
9. **No Predictive Claims in Sprint 01:** Sprint 01 focuses on descriptive and discovery research, not price forecasting.

## Architecture & Workflow

```bash
# 1. Download BTC 5-minute historical data (2026-01-01 to present)
python scripts/download_btc.py

# 2. Run data validation & generate quality report
python scripts/validate_data.py

# 3. Aggregate canonical 5m candles into 15m, 1h, 4h, 1d
python scripts/build_timeframes.py

# 4. Run feature extraction, regime classification, event discovery & behavior mapping
python scripts/run_research.py
```

Or via unified CLI:
```bash
python -m coin_behavior_engine all
```

## Running Tests

```bash
pytest -v tests/
```
