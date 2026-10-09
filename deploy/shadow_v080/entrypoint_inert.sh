#!/bin/sh
# ==============================================================================
# SPRINT 09.13 / APPROVAL 2 — FAIL-CLOSED INERT SERVICE ENTRYPOINT
# ==============================================================================
# Verifies all safety invariants before terminating cleanly with exit code 0.
# Zero continuous background loop.
# Zero Binance API requests.
# Zero prospective scoring.
# Zero trading capability.
# ==============================================================================

set -eu

echo "=================================================================="
echo "CBE-0.8.0 SHADOW COLLECTOR: INERT COOLIFY LANDING VERIFICATION"
echo "Security Profile: APPROVAL_2 (Inert Staging Only)"
echo "Network Mode: DISABLED (network_mode: none)"
echo "Trading: PERMANENTLY DISABLED"
echo "Binance Feed: DISABLED (Requires separate APPROVAL 3)"
echo "Prospective Scoring: DISABLED (Requires separate APPROVAL 4)"
echo "=================================================================="

# Execute Python safety contract verification
python3 -m coin_behavior_engine.shadow_v080.deploy_safety

VERIFY_EXIT=$?
if [ $VERIFY_EXIT -ne 0 ]; then
    echo "[CRITICAL SAFETY FAILURE] Safety contract verification failed with code $VERIFY_EXIT."
    echo "Failing closed immediately. No observation or background worker will start."
    exit 1
fi

echo "Inert verification complete. Service is quiescent and verified safe."
exit 0
