#!/usr/bin/env python3
"""CBE-0.8.0 Live Capture Research Readiness & Evidence Integrity Audit CLI.

Sprint 11.02E: Live Capture Research Readiness & Evidence Audit.

Audits:
1. Cryptographic hash-chain continuity for raw candles and recovery journals.
2. Gap recovery journal and metadata cross-validation.
3. 5-minute temporal continuity, timestamp alignment, and gap detection.
4. Independent 288-bar full-warmup research eligibility determination.
5. Authorization safety interlocks (trading disabled, prospective scoring disabled).
6. Optional parity check with MarketCaptureEngine state reconstruction.

Strictly read-only: does not modify evidence, does not rebuild indexes, does not truncate files.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from coin_behavior_engine.shadow_v080.research_readiness_auditor import (
    AuditVerdict,
    ResearchReadinessAuditor,
    main,
)

if __name__ == "__main__":
    sys.exit(main())
