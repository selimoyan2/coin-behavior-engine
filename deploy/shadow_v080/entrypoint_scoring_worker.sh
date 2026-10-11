#!/bin/sh
# ==============================================================================
# SPRINT 09.18 — ISOLATED PROSPECTIVE SCORING WORKER ENTRYPOINT
# ==============================================================================
# Dedicated entrypoint for offline prospective scoring and outcome resolution.
# Fails closed immediately if Approval 4 is not authorized for prospective live mode.
# ==============================================================================

set -eu

echo "=================================================================="
echo "CBE-0.8.0 PROSPECTIVE SCORING WORKER: STARTUP & PRE-FLIGHT CHECK"
echo "Security Profile: APPROVAL_4 (Isolated Prospective Scoring Worker)"
echo "Trading: PERMANENTLY DISABLED"
echo "Network: NONE (Strictly offline isolated execution)"
echo "Evidence Ledger: READ-ONLY MOUNT"
echo "=================================================================="

exec python3 -m coin_behavior_engine.shadow_v080.scoring_worker "$@"
