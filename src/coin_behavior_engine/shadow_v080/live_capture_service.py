"""CBE-0.8.0 Live Market Capture Service & Safety Interlock.

Sprint 09.14.2 / Approval 3 Preparation.

Enforces:
1. Strict fail-closed pre-flight validation:
   - CBE_APPROVAL_3_AUTHORIZED must be explicitly 'true'.
   - CBE_BINANCE_COLLECTION_ENABLED must be 'true'.
   - CBE_TRADING_DISABLED must be 'true'.
   - CBE_PROSPECTIVE_OBSERVATION_ENABLED must be 'false'.
   - CBE_APPROVAL_4_AUTHORIZED must NOT be 'true'.
   - CBE_RECORD_LABEL must be 'LIVE_BINANCE_SPOT'.
2. Bounded execution lifecycle with clean SIGINT/SIGTERM shutdown handlers.
3. Durable evidence persistence via MarketCaptureEngineV080 and RawMarketEvidenceStore.
4. Downstream research eligibility monitoring (>=288 contiguous closed candles).
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080
from coin_behavior_engine.shadow_v080.market_data_contract import ProvenanceSource
from coin_behavior_engine.shadow_v080.transport_adapter import (
    BaseMarketDataTransport,
    BinanceSpotRestAdapter,
    BinanceSpotWebSocketAdapter,
    SafetyInterlockError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [LiveCaptureService] %(message)s",
)
logger = logging.getLogger("LiveCaptureService")


def verify_live_capture_preflight() -> Tuple[bool, List[str]]:
    """Verify that all strict environment safety interlocks for live capture are satisfied.

    Returns:
        (is_valid, violations_list)
    """
    violations: List[str] = []

    # 1. Approval 3 explicit authorization
    if os.environ.get("CBE_APPROVAL_3_AUTHORIZED") != "true":
        violations.append(
            "CBE_APPROVAL_3_AUTHORIZED is not 'true'. Approval 3 is NOT authorized; live Binance capture is prohibited."
        )

    # 2. Binance collection enabled
    if os.environ.get("CBE_BINANCE_COLLECTION_ENABLED") != "true":
        violations.append(
            "CBE_BINANCE_COLLECTION_ENABLED is not 'true'. Binance collection is disabled."
        )

    # 3. Trading permanently disabled
    if os.environ.get("CBE_TRADING_DISABLED") != "true":
        violations.append(
            "CBE_TRADING_DISABLED is not 'true'. Trading interlock violated; trading is prohibited."
        )

    # 4. Prospective scoring disabled (Approval 4 isolated)
    if os.environ.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") != "false":
        violations.append(
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED must be 'false'. Prospective scoring must be disabled."
        )

    if os.environ.get("CBE_APPROVAL_4_AUTHORIZED") == "true":
        violations.append(
            "CBE_APPROVAL_4_AUTHORIZED must not be 'true'. Approval 4 is pending."
        )

    # 5. Record label check
    record_label = os.environ.get("CBE_RECORD_LABEL")
    if record_label != "LIVE_BINANCE_SPOT":
        violations.append(
            f"CBE_RECORD_LABEL must be 'LIVE_BINANCE_SPOT' (got '{record_label}')."
        )

    return len(violations) == 0, violations


class LiveCaptureService:
    """Dedicated production-grade staging service for live Binance market data capture."""

    def __init__(
        self,
        config: Optional[ShadowCollectorConfig] = None,
        transport: Optional[BaseMarketDataTransport] = None,
        rest_adapter: Optional[BinanceSpotRestAdapter] = None,
    ):
        is_valid, violations = verify_live_capture_preflight()
        if not is_valid:
            error_msg = "; ".join(violations)
            logger.critical(f"Safety interlock violation: {error_msg}")
            raise SafetyInterlockError(f"LiveCaptureService fail-closed: {error_msg}")

        if config is None:
            symbol = os.environ.get("CBE_SYMBOL", "BTCUSDT")
            interval = os.environ.get("CBE_INTERVAL", "5m")
            shadow_data_dir = Path(os.environ.get("CBE_SHADOW_DATA_DIR", "/app/data/live_capture"))
            raw_market_dir = Path(os.environ.get("CBE_RAW_MARKET_DIR", str(shadow_data_dir / "raw_market")))
            quarantine_dir = Path(os.environ.get("CBE_QUARANTINE_DIR", str(shadow_data_dir / "quarantine")))

            self.config = ShadowCollectorConfig(
                symbol=symbol,
                interval=interval,
                approval_3_authorized=True,
                approval_4_authorized=False,
                live_shadow_enabled=True,
                network_enabled=True,
                trading_enabled=False,
                shadow_data_dir=shadow_data_dir,
            )
            # Override directories if explicitly specified
            self.config.raw_market_dir = raw_market_dir
            self.config.quarantine_dir = quarantine_dir
        else:
            self.config = config

        self.transport = transport or BinanceSpotWebSocketAdapter(self.config)
        self.rest_adapter = rest_adapter
        self.engine = MarketCaptureEngineV080(
            config=self.config,
            transport=self.transport,
            default_provenance=ProvenanceSource.LIVE_BINANCE_SPOT.value,
        )

        self._stop_requested = False
        self._install_signal_handlers()

    def _install_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, AttributeError) as exc:
            logger.debug(f"Signal handlers not installed: {exc}")

    def _handle_signal(self, signum: int, frame: Any) -> None:
        signame = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        logger.info(f"Signal received: {signame}. Initiating graceful service shutdown...")
        self.stop()

    def stop(self) -> None:
        """Gracefully terminate engine, close transport, and release resources."""
        self._stop_requested = True
        try:
            self.engine.stop()
        except Exception as exc:
            logger.warning(f"Error stopping capture engine: {exc}")

        try:
            self.engine.evidence_store.close()
        except Exception as exc:
            logger.warning(f"Error closing evidence store: {exc}")

        logger.info("LiveCaptureService stopped successfully.")

    def run(self, max_ticks: Optional[int] = None) -> int:
        """Run the service loop until stopped or max_ticks reached."""
        logger.info(
            f"Starting LiveCaptureService for {self.config.symbol} {self.config.interval} "
            f"(full warmup threshold: {self.config.full_warmup_bars} bars)..."
        )
        self.engine.start()

        ticks_processed = 0
        last_log_time = time.time()

        try:
            while not self._stop_requested:
                if max_ticks is not None and ticks_processed >= max_ticks:
                    logger.info(f"Max ticks reached ({max_ticks}). Normal termination.")
                    break

                tick_result = self.engine.process_next_tick()
                status = tick_result.get("status")

                if status == "NO_MESSAGE":
                    time.sleep(0.1)
                else:
                    ticks_processed += 1
                    # Handle automatic gap recovery if REST adapter is attached
                    if tick_result.get("gap_detected") and self.rest_adapter is not None:
                        gap_event = tick_result.get("gap_event")
                        if gap_event:
                            gap_id = gap_event["gap_id"]
                            logger.info(f"Sequence gap detected ({gap_id}). Triggering REST recovery...")
                            ok, msg = self.engine.recover_gap_via_rest(gap_id, self.rest_adapter)
                            if ok:
                                logger.info(f"Gap {gap_id} successfully recovered via REST.")
                            else:
                                logger.warning(f"REST gap recovery failed for {gap_id}: {msg}")

                now = time.time()
                if now - last_log_time >= 60.0:
                    last_log_time = now
                    report = self.engine.get_summary_report()
                    logger.info(
                        f"Status: warmup={report['warmup_status']} | "
                        f"contiguous={report['contiguous_bars_count']} | "
                        f"persisted={report['total_persisted']} | "
                        f"quarantined={report['total_quarantined']} | "
                        f"eligible={report['is_research_eligible']}"
                    )

        except Exception as exc:
            logger.critical(f"Unhandled exception in service loop: {exc}", exc_info=True)
            self.stop()
            return 1

        self.stop()
        return 0


def main() -> int:
    """CLI / container entrypoint with fail-closed safety gating."""
    logger.info("=== CBE-0.8.0 Live Market Capture Service Starting ===")

    is_valid, violations = verify_live_capture_preflight()
    if not is_valid:
        print("=" * 70, file=sys.stderr)
        print("[CRITICAL SAFETY INTERLOCK] APPROVAL 3 PRE-FLIGHT VERIFICATION FAILED", file=sys.stderr)
        print("Service is strictly FAIL-CLOSED. Live collection is PROHIBITED.", file=sys.stderr)
        print("Violations detected:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        logger.critical(f"Pre-flight verification failed with {len(violations)} violations. Exiting.")
        return 1

    try:
        service = LiveCaptureService()
        return service.run()
    except Exception as exc:
        logger.critical(f"Fatal error during service initialization or run: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
