"""CBE Conformal Calibration & Model Reliability Module (Sprint 10.01).

Provides:
- Causal split conformal prediction and calibration for frozen model intervals.
- Independent baseline reproduction of interval undercoverage.
- Horizon-level breakdown across all 8 prediction horizons.
- Moving block bootstrap for autocorrelated time series.
- Forensic audit of market-state regime classifier locks.
- Probability provenance taxonomy.
"""

from __future__ import annotations

from coin_behavior_engine.calibration.conformal_calibrator import (
    CalibrationMethodType,
    CausalConformalCalibrator,
    ConformalCalibrationContract,
    HorizonCoverageResult,
    HorizonDecisionGate,
    ProbabilityProvenanceType,
    RegimeCoverageDiagnostic,
    RegimeClassifierAuditRecord,
    Sprint1001MasterReport,
)
from coin_behavior_engine.calibration.independent_verifier import (
    ChronologicalCausalityAudit,
    CorrectedCausalRegimeClassifierCandidate,
    CorrectedRegimeResult,
    EffectiveSampleSizeSensitivity,
    IndependentCalibrationVerifier,
    MethodSelectionAudit,
    SourceRecordReconciliation,
    Sprint1002MasterReport,
)

__all__ = [
    "CalibrationMethodType",
    "CausalConformalCalibrator",
    "ConformalCalibrationContract",
    "HorizonCoverageResult",
    "HorizonDecisionGate",
    "ProbabilityProvenanceType",
    "RegimeCoverageDiagnostic",
    "RegimeClassifierAuditRecord",
    "Sprint1001MasterReport",
    "ChronologicalCausalityAudit",
    "CorrectedCausalRegimeClassifierCandidate",
    "CorrectedRegimeResult",
    "EffectiveSampleSizeSensitivity",
    "IndependentCalibrationVerifier",
    "MethodSelectionAudit",
    "SourceRecordReconciliation",
    "Sprint1002MasterReport",
]
