"""CLI Entrypoint for CBE-0.8.0 Shadow Collector.

Enforces:
- Hard safety interlock on live execution.
- Offline replay and validation modes.
- Observation-only status reporting.
"""

from __future__ import annotations

import argparse
import logging
import sys

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cbe_shadow_cli")


def main():
    parser = argparse.ArgumentParser(description="CBE-0.8.0 Shadow Collector CLI")
    parser.add_argument(
        "--mode",
        choices=["status", "replay", "live"],
        default="status",
        help="Execution mode (status, replay, live)",
    )
    parser.add_argument("--fixture", type=str, default=None, help="Path to offline parquet fixture")
    args = parser.parse_args()

    config = ShadowCollectorConfig()

    if args.mode == "live":
        logger.error(
            "HARD SAFETY INTERLOCK: Live shadow observation is strictly disabled by default. "
            "Activation requires explicit pre-activation audit and authorization."
        )
        sys.exit(1)

    if args.mode == "status":
        logger.info(f"CBE-0.8.0 Shadow Collector Status: CONFIGURED (Offline Only)")
        logger.info(f"Candidate Version: {config.candidate_model_version}")
        logger.info(f"Network Enabled: {config.network_enabled}")
        logger.info(f"Live Shadow Enabled: {config.live_shadow_enabled}")
        logger.info(f"Trading Enabled: {config.trading_enabled}")
        sys.exit(0)

    if args.mode == "replay":
        logger.info("Offline replay mode requested. Use automated test harness or pipeline.")
        sys.exit(0)


if __name__ == "__main__":
    main()
