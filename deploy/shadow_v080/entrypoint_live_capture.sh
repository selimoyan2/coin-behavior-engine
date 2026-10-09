#!/bin/sh
# ==============================================================================
# SPRINT 09.14.2 / APPROVAL 3 — LIVE CAPTURE SERVICE CONTAINER ENTRYPOINT
# ==============================================================================
# Dedicated entrypoint for live Binance Spot 5m market data capture.
# Fails closed immediately if Approval 3 is not authorized.
# ==============================================================================

set -eu

echo "=================================================================="
echo "CBE-0.8.0 LIVE CAPTURE SERVICE: STARTUP & PRE-FLIGHT CHECK"
echo "Security Profile: APPROVAL_3 (Binance Spot 5m Market Ingestion)"
echo "Trading: PERMANENTLY DISABLED"
echo "Prospective Scoring: DISABLED (Requires separate APPROVAL 4)"
echo "=================================================================="

exec python3 -m coin_behavior_engine.shadow_v080.live_capture_service "$@"
