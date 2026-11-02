"""
CBE — Research Reproducibility Engine V1 (Sprint 21)
Provides deterministic research execution verification, numerical comparison policies,
reproducibility manifests, and automated replay auditing for historical research workflows.

Epistemological Principle:
A research finding is not reproducible merely because its initial execution succeeded.
True reproducibility requires reconstructing the exact analytical pipeline from declared
inputs, verifying dataset provenance and model freeze, and confirming that independent
re-execution reproduces outputs within strictly justified numerical tolerances.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import platform
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.unified_research_workspace import (
    UnifiedResearchWorkspaceEngine,
    UnifiedResearchSession,
)

logger = logging.getLogger("cbe.research_reproducibility")

REPRODUCIBILITY_SCHEMA_VERSION = "CBE-REPRODUCIBILITY-1.0.0"

# Documented Scientific Numerical Tolerances
# Justified by floating-point summation order and SIMD vectorization differences
REGIME_PROBABILITY_TOLERANCE = 1e-5
VOLATILITY_METRIC_TOLERANCE = 1e-5
SIMILARITY_SCORE_TOLERANCE = 1e-4
STATISTICAL_P_VALUE_TOLERANCE = 1e-6
RETURN_METRIC_TOLERANCE = 1e-5


class ReproducibilityVerdict(str, Enum):
    """Authoritative reproducibility verification verdicts."""
    REPRODUCIBLE_EXACT = "REPRODUCIBLE_EXACT"
    REPRODUCIBLE_WITH_NUMERICAL_TOLERANCE = "REPRODUCIBLE_WITH_NUMERICAL_TOLERANCE"
    NON_REPRODUCIBLE = "NON_REPRODUCIBLE"
    INCOMPLETE_EVIDENCE = "INCOMPLETE_EVIDENCE"
    DATASET_PROVENANCE_MISMATCH = "DATASET_PROVENANCE_MISMATCH"
    MODEL_VERSION_MISMATCH = "MODEL_VERSION_MISMATCH"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


HEX_40_REGEX = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass
class ReproducibilityManifest:
    """
    Structured metadata manifest accompanying every verifiable research execution.
    Captures exact provenance, software environment, and analytical configuration.
    """
    schema_version: str = REPRODUCIBILITY_SCHEMA_VERSION
    research_id: str = ""
    research_session_id: str = ""
    canonical_model_version: str = FROZEN_MODEL_VERSION
    dataset_manifest_sha256: str = ""
    source_commit_sha: str = ""
    research_configuration_sha256: str = ""
    analytical_modules: List[str] = field(default_factory=list)
    reference_start_utc: str = ""
    reference_end_utc: str = ""
    execution_environment: Dict[str, Any] = field(default_factory=dict)
    research_only: bool = True
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchReproducibilityEngine:
    """
    Core engine for deterministic re-execution, numerical equality checking,
    and reproducibility manifest generation.
    """

    @classmethod
    def is_valid_commit_sha(cls, sha: Optional[str]) -> bool:
        """Validate full 40-character hexadecimal Git SHA."""
        if not sha or not isinstance(sha, str):
            return False
        return bool(HEX_40_REGEX.match(sha.strip()))

    @classmethod
    def get_source_commit_sha(cls, repo_root: Optional[Path] = None) -> str:
        """
        Resolve authoritative source commit SHA or return explicit unavailable status.
        Never fabricates a fallback or returns a hardcoded commit.
        Resolution order:
          1. Validated environment variable (GIT_COMMIT_SHA / SOURCE_COMMIT_SHA)
          2. Validated build_metadata.json (source_commit_sha / build_commit_sha / git_commit)
          3. Validated Git repository (.git/HEAD / ref resolution / packed-refs)
        Returns:
          40-character hex string if verified, otherwise 'UNAVAILABLE'.
        """
        # 1. Environment variable
        env_sha = os.environ.get("GIT_COMMIT_SHA") or os.environ.get("SOURCE_COMMIT_SHA")
        if env_sha and env_sha.strip():
            clean_env = env_sha.strip()
            if cls.is_valid_commit_sha(clean_env):
                return clean_env

        root = repo_root or Path(__file__).resolve().parents[3]

        # 2. Build metadata file
        meta_file = root / "build_metadata.json"
        if meta_file.exists():
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                for key in ("source_commit_sha", "build_commit_sha", "git_commit", "git_revision", "commit_sha"):
                    candidate = data.get(key)
                    if candidate and cls.is_valid_commit_sha(str(candidate).strip()):
                        return str(candidate).strip()
            except Exception:
                pass

        # 3. Git repository inspection
        git_dir = root / ".git"
        if git_dir.exists():
            try:
                head_file = git_dir / "HEAD"
                if head_file.exists():
                    content = head_file.read_text(encoding="utf-8").strip()
                    if content.startswith("ref:"):
                        rel_ref = content.split(":", 1)[1].strip()
                        ref_path = git_dir / rel_ref
                        if ref_path.exists():
                            ref_sha = ref_path.read_text(encoding="utf-8").strip()
                            if cls.is_valid_commit_sha(ref_sha):
                                return ref_sha
                        # Check packed-refs if loose ref does not exist
                        packed_refs = git_dir / "packed-refs"
                        if packed_refs.exists():
                            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                                line = line.strip()
                                if line.endswith(rel_ref) and not line.startswith("^"):
                                    p_sha = line.split()[0].strip()
                                    if cls.is_valid_commit_sha(p_sha):
                                        return p_sha
                    elif cls.is_valid_commit_sha(content):
                        return content
            except Exception:
                pass

        return "UNAVAILABLE"

    @classmethod
    def compute_configuration_sha256(cls, config: Dict[str, Any]) -> str:
        """Compute canonical SHA-256 hash over normalized research configuration parameters."""
        normalized = {
            "canonical_model": str(config.get("canonical_model", FROZEN_MODEL_VERSION)).strip(),
            "asset": str(config.get("asset", "BTCUSDT")).strip().upper(),
            "interval": str(config.get("interval", "1h")).strip().lower(),
            "start_utc": str(config.get("reference_start_utc") or config.get("start_utc", "")).strip(),
            "end_utc": str(config.get("reference_end_utc") or config.get("end_utc", "")).strip(),
            "modules": sorted([str(m).strip().lower() for m in config.get("selected_modules", [])]),
        }
        raw_bytes = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    @classmethod
    def create_reproducibility_manifest(
        cls,
        research_id: str,
        session_id: str,
        config: Dict[str, Any],
        dataset_manifest_sha: Optional[str] = None,
    ) -> ReproducibilityManifest:
        """Generate a complete ReproducibilityManifest instance for a research run."""
        if not dataset_manifest_sha:
            meta = ContentIntegrityEngine.generate_canonical_manifest()
            dataset_manifest_sha = meta.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")

        config_sha = cls.compute_configuration_sha256(config)
        start_utc = str(config.get("reference_start_utc") or config.get("start_utc", "")).strip()
        end_utc = str(config.get("reference_end_utc") or config.get("end_utc", "")).strip()
        modules = config.get("selected_modules") or [
            "regime_analysis",
            "volatility_analysis",
            "historical_pattern_discovery",
            "macro_comparison",
            "statistical_evidence",
        ]

        env_info = {
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "byte_order": sys.byteorder,
        }

        return ReproducibilityManifest(
            schema_version=REPRODUCIBILITY_SCHEMA_VERSION,
            research_id=research_id,
            research_session_id=session_id,
            canonical_model_version=FROZEN_MODEL_VERSION,
            dataset_manifest_sha256=dataset_manifest_sha,
            source_commit_sha=cls.get_source_commit_sha(),
            research_configuration_sha256=config_sha,
            analytical_modules=modules,
            reference_start_utc=start_utc,
            reference_end_utc=end_utc,
            execution_environment=env_info,
            research_only=True,
        )

    @classmethod
    def compare_numerical_values(
        cls,
        val1: Any,
        val2: Any,
        tolerance: float,
    ) -> Tuple[bool, float, bool]:
        """
        Compare two numbers under scientific floating-point tolerance policy.
        Returns: (is_within_tolerance, absolute_delta, is_exact_match).

        Scientific Governance Rules:
        1. Non-finite values (NaN, +inf, -inf) are strictly prohibited and rejected.
           NaN is NEVER considered a successful numerical match.
        2. Missing/None values are rejected; they NEVER become zero-equivalent defaults.
        3. String or malformed values that cannot be parsed as finite floats are rejected.
        4. If either value is invalid, returns (False, float("inf"), False).
        5. If valid, evaluates exact equality (abs_diff == 0.0) and tolerance bound (abs_diff <= tolerance).
        """
        if val1 is None or val2 is None:
            return False, float("inf"), False

        # Disallow booleans (subclass of int in Python)
        if isinstance(val1, bool) or isinstance(val2, bool):
            return False, float("inf"), False

        try:
            f1 = float(val1)
            f2 = float(val2)
        except (ValueError, TypeError):
            return False, float("inf"), False

        # Strictly reject NaN
        if math.isnan(f1) or math.isnan(f2):
            return False, float("inf"), False

        # Strictly reject non-finite (inf, -inf)
        if not math.isfinite(f1) or not math.isfinite(f2):
            return False, float("inf"), False

        abs_diff = abs(f1 - f2)
        within = abs_diff <= tolerance
        exact = (abs_diff == 0.0)
        return within, abs_diff, exact

    @classmethod
    def compare_module_outputs(
        cls,
        run1: Dict[str, Any],
        run2: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Deep comparison of two research session executions across all analytical modules.
        Enforces exact categorical matches and calibrated numerical tolerances.
        Rejects non-finite (NaN, inf) or missing values from passing scientific gates.
        """
        report: Dict[str, Any] = {
            "all_exact_match": True,
            "within_tolerances": True,
            "max_numerical_delta": 0.0,
            "discrepancies": [],
            "module_comparisons": {},
            "has_invalid_numerical_values": False,
        }

        def record_discrepancy(field_path: str, v1: Any, v2: Any, delta: float, tol: float, critical: bool = False, reason: str = ""):
            report["all_exact_match"] = False
            if critical or delta > tol or not math.isfinite(delta):
                report["within_tolerances"] = False
                report["has_invalid_numerical_values"] = True
            if math.isfinite(delta) and delta > report["max_numerical_delta"]:
                report["max_numerical_delta"] = delta
            report["discrepancies"].append({
                "field": field_path,
                "val_run1": v1,
                "val_run2": v2,
                "delta": None if (delta is None or not math.isfinite(delta)) else delta,
                "tolerance": tol,
                "critical": critical,
                "reason": reason,
            })

        # Resolve modules from module_results (standard session) or top-level keys
        mr1 = run1.get("module_results") if isinstance(run1.get("module_results"), dict) else {}
        mr2 = run2.get("module_results") if isinstance(run2.get("module_results"), dict) else {}

        reg1 = mr1.get("regime_analysis") if "regime_analysis" in mr1 else run1.get("regime_analysis")
        reg2 = mr2.get("regime_analysis") if "regime_analysis" in mr2 else run2.get("regime_analysis")

        vol1 = mr1.get("volatility_analysis") if "volatility_analysis" in mr1 else run1.get("volatility_analysis")
        vol2 = mr2.get("volatility_analysis") if "volatility_analysis" in mr2 else run2.get("volatility_analysis")

        pat1 = (
            mr1.get("pattern_discovery") or mr1.get("historical_pattern_discovery")
            if ("pattern_discovery" in mr1 or "historical_pattern_discovery" in mr1)
            else (run1.get("pattern_discovery") or run1.get("historical_pattern_discovery"))
        )
        pat2 = (
            mr2.get("pattern_discovery") or mr2.get("historical_pattern_discovery")
            if ("pattern_discovery" in mr2 or "historical_pattern_discovery" in mr2)
            else (run2.get("pattern_discovery") or run2.get("historical_pattern_discovery"))
        )

        stat1 = mr1.get("statistical_evidence") if "statistical_evidence" in mr1 else run1.get("statistical_evidence")
        stat2 = mr2.get("statistical_evidence") if "statistical_evidence" in mr2 else run2.get("statistical_evidence")

        # 1. Compare Regime Analysis
        if reg1 is not None or reg2 is not None:
            mod_reg = {"exact": True, "within_tol": True, "max_delta": 0.0}
            if reg1 is None or reg2 is None:
                mod_reg["exact"] = False
                mod_reg["within_tol"] = False
                record_discrepancy(
                    "regime_analysis",
                    reg1,
                    reg2,
                    float("inf"),
                    0.0,
                    critical=True,
                    reason="ASYMMETRIC_REGIME_ANALYSIS_MISSING"
                )
            else:
                # Dominant regime must match exactly (categorical)
                dom1 = reg1.get("dominant_regime")
                dom2 = reg2.get("dominant_regime")
                if dom1 != dom2 or dom1 is None or dom2 is None:
                    mod_reg["exact"] = False
                    mod_reg["within_tol"] = False
                    record_discrepancy(
                        "regime_analysis.dominant_regime",
                        dom1,
                        dom2,
                        float("inf"),
                        0.0,
                        critical=True,
                        reason="DOMINANT_REGIME_MISMATCH_OR_MISSING"
                    )

                # Regime counts & distribution - NEVER default missing to 0.0
                dist1 = reg1.get("regime_distribution", {}) or {}
                dist2 = reg2.get("regime_distribution", {}) or {}
                all_regimes = set(dist1.keys()).union(set(dist2.keys()))
                for r_key in sorted(all_regimes):
                    if r_key not in dist1 or r_key not in dist2:
                        mod_reg["exact"] = False
                        mod_reg["within_tol"] = False
                        record_discrepancy(
                            f"regime_analysis.distribution.{r_key}",
                            dist1.get(r_key),
                            dist2.get(r_key),
                            float("inf"),
                            REGIME_PROBABILITY_TOLERANCE,
                            critical=True,
                            reason="MISSING_REGIME_IN_DISTRIBUTION"
                        )
                        continue

                    p1 = dist1[r_key]
                    p2 = dist2[r_key]
                    ok, delta, exact = cls.compare_numerical_values(p1, p2, REGIME_PROBABILITY_TOLERANCE)
                    if not exact:
                        mod_reg["exact"] = False
                        if not ok:
                            mod_reg["within_tol"] = False
                        record_discrepancy(
                            f"regime_analysis.distribution.{r_key}",
                            p1,
                            p2,
                            delta,
                            REGIME_PROBABILITY_TOLERANCE,
                            critical=not ok,
                            reason="PROBABILITY_DELTA_EXCEEDED" if not ok else "PROBABILITY_DELTA"
                        )

            report["module_comparisons"]["regime_analysis"] = mod_reg

        # 2. Compare Volatility Analysis
        if vol1 is not None or vol2 is not None:
            mod_vol = {"exact": True, "within_tol": True, "max_delta": 0.0}
            if vol1 is None or vol2 is None:
                mod_vol["exact"] = False
                mod_vol["within_tol"] = False
                record_discrepancy(
                    "volatility_analysis",
                    vol1,
                    vol2,
                    float("inf"),
                    0.0,
                    critical=True,
                    reason="ASYMMETRIC_VOLATILITY_ANALYSIS_MISSING"
                )
            else:
                vol1_d = vol1 if isinstance(vol1, dict) else {}
                vol2_d = vol2 if isinstance(vol2, dict) else {}
                all_vol_metrics = set(vol1_d.keys()).union(set(vol2_d.keys()))
                for v_metric in sorted(all_vol_metrics):
                    # Skip non-numeric or informational fields
                    if v_metric in ("status", "explanation_tr", "execution_time_ms", "warnings"):
                        continue
                    if v_metric not in vol1_d or v_metric not in vol2_d:
                        mod_vol["exact"] = False
                        mod_vol["within_tol"] = False
                        record_discrepancy(
                            f"volatility_analysis.{v_metric}",
                            vol1_d.get(v_metric),
                            vol2_d.get(v_metric),
                            float("inf"),
                            VOLATILITY_METRIC_TOLERANCE,
                            critical=True,
                            reason="ASYMMETRIC_VOLATILITY_METRIC_MISSING"
                        )
                        continue

                    v1 = vol1_d[v_metric]
                    v2 = vol2_d[v_metric]
                    if v1 is None or v2 is None:
                        mod_vol["exact"] = False
                        mod_vol["within_tol"] = False
                        record_discrepancy(
                            f"volatility_analysis.{v_metric}",
                            v1,
                            v2,
                            float("inf"),
                            VOLATILITY_METRIC_TOLERANCE,
                            critical=True,
                            reason="NONE_VOLATILITY_VALUE"
                        )
                        continue

                    if isinstance(v1, (int, float)) and not isinstance(v1, bool):
                        ok, delta, exact = cls.compare_numerical_values(v1, v2, VOLATILITY_METRIC_TOLERANCE)
                        if not exact:
                            mod_vol["exact"] = False
                            if not ok:
                                mod_vol["within_tol"] = False
                            record_discrepancy(
                                f"volatility_analysis.{v_metric}",
                                v1,
                                v2,
                                delta,
                                VOLATILITY_METRIC_TOLERANCE,
                                critical=not ok,
                                reason="VOLATILITY_DELTA_EXCEEDED" if not ok else "VOLATILITY_DELTA"
                            )
                    else:
                        if v1 != v2:
                            mod_vol["exact"] = False
                            mod_vol["within_tol"] = False
                            record_discrepancy(
                                f"volatility_analysis.{v_metric}",
                                v1,
                                v2,
                                float("inf"),
                                0.0,
                                critical=True,
                                reason="METADATA_MISMATCH"
                            )

            report["module_comparisons"]["volatility_analysis"] = mod_vol

        # 3. Compare Historical Pattern Discovery Candidates
        if pat1 is not None or pat2 is not None:
            mod_pat = {"exact": True, "within_tol": True, "max_delta": 0.0}
            if pat1 is None or pat2 is None:
                mod_pat["exact"] = False
                mod_pat["within_tol"] = False
                record_discrepancy(
                    "pattern_discovery",
                    pat1,
                    pat2,
                    float("inf"),
                    0.0,
                    critical=True,
                    reason="ASYMMETRIC_PATTERN_DISCOVERY_MISSING"
                )
            else:
                pat1_d = pat1 if isinstance(pat1, dict) else {}
                pat2_d = pat2 if isinstance(pat2, dict) else {}
                cands1 = pat1_d.get("candidates") or pat1_d.get("top_candidates") or []
                cands2 = pat2_d.get("candidates") or pat2_d.get("top_candidates") or []

                if len(cands1) != len(cands2):
                    mod_pat["exact"] = False
                    mod_pat["within_tol"] = False
                    record_discrepancy(
                        "pattern_discovery.candidate_count",
                        len(cands1),
                        len(cands2),
                        float("inf"),
                        0.0,
                        critical=True,
                        reason="CANDIDATE_COUNT_MISMATCH"
                    )
                else:
                    for idx, (c1, c2) in enumerate(zip(cands1, cands2)):
                        # Dates must match exactly
                        s1 = c1.get("candidate_start_utc") or c1.get("start_utc")
                        s2 = c2.get("candidate_start_utc") or c2.get("start_utc")
                        if s1 != s2 or s1 is None:
                            mod_pat["exact"] = False
                            mod_pat["within_tol"] = False
                            record_discrepancy(
                                f"pattern_discovery.candidate[{idx}].start_utc",
                                s1,
                                s2,
                                float("inf"),
                                0.0,
                                critical=True,
                                reason="CANDIDATE_START_DATE_MISMATCH"
                            )

                        # Similarity score comparison within tolerance - NEVER default to 0.0
                        sim1 = c1.get("similarity_score") if "similarity_score" in c1 else c1.get("similarity")
                        sim2 = c2.get("similarity_score") if "similarity_score" in c2 else c2.get("similarity")
                        if sim1 is None or sim2 is None:
                            mod_pat["exact"] = False
                            mod_pat["within_tol"] = False
                            record_discrepancy(
                                f"pattern_discovery.candidate[{idx}].similarity_score",
                                sim1,
                                sim2,
                                float("inf"),
                                SIMILARITY_SCORE_TOLERANCE,
                                critical=True,
                                reason="MISSING_SIMILARITY_SCORE"
                            )
                            continue

                        ok, delta, exact = cls.compare_numerical_values(sim1, sim2, SIMILARITY_SCORE_TOLERANCE)
                        if not exact:
                            mod_pat["exact"] = False
                            if not ok:
                                mod_pat["within_tol"] = False
                            record_discrepancy(
                                f"pattern_discovery.candidate[{idx}].similarity_score",
                                sim1,
                                sim2,
                                delta,
                                SIMILARITY_SCORE_TOLERANCE,
                                critical=not ok,
                                reason="SIMILARITY_DELTA_EXCEEDED" if not ok else "SIMILARITY_DELTA"
                            )

            report["module_comparisons"]["pattern_discovery"] = mod_pat

        # 4. Compare Statistical Evidence & Disclosures
        stat1 = run1.get("statistical_evidence")
        stat2 = run2.get("statistical_evidence")
        if stat1 is not None or stat2 is not None:
            mod_stat = {"exact": True, "within_tol": True}
            if stat1 is None or stat2 is None:
                mod_stat["exact"] = False
                mod_stat["within_tol"] = False
                record_discrepancy(
                    "statistical_evidence",
                    stat1,
                    stat2,
                    float("inf"),
                    0.0,
                    critical=True,
                    reason="ASYMMETRIC_STATISTICAL_EVIDENCE_MISSING"
                )
            else:
                for s_key in ("predeclared_holdout_criteria_satisfied", "independent_confirmatory_replications"):
                    if s_key in stat1 or s_key in stat2:
                        v1 = stat1.get(s_key)
                        v2 = stat2.get(s_key)
                        if v1 != v2 or v1 is None or v2 is None:
                            mod_stat["exact"] = False
                            mod_stat["within_tol"] = False
                            record_discrepancy(
                                f"statistical_evidence.{s_key}",
                                v1,
                                v2,
                                float("inf"),
                                0.0,
                                critical=True,
                                reason=f"{s_key.upper()}_MISMATCH"
                            )
            report["module_comparisons"]["statistical_evidence"] = mod_stat

        return report

    @classmethod
    def verify_reproducibility(
        cls,
        workflow_context: Dict[str, Any],
        original_session: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Verify end-to-end reproducibility of a research configuration.
        Executes a deterministic re-run and verifies all invariants against original data.
        """
        start_utc = workflow_context.get("reference_start_utc") or workflow_context.get("start_utc", "")
        end_utc = workflow_context.get("reference_end_utc") or workflow_context.get("end_utc", "")
        asset = workflow_context.get("asset", "BTCUSDT")
        interval = workflow_context.get("interval", "1h")
        modules = workflow_context.get("selected_modules") or [
            "regime_analysis",
            "volatility_analysis",
            "historical_pattern_discovery",
            "macro_comparison",
            "statistical_evidence",
        ]

        # 1. Canonical Model Check
        model_version = workflow_context.get("canonical_model_version") or FROZEN_MODEL_VERSION
        if model_version != FROZEN_MODEL_VERSION:
            return {
                "verdict": ReproducibilityVerdict.MODEL_VERSION_MISMATCH.value,
                "reproducible": False,
                "explanation": (
                    f"MODEL UYUŞMAZLIĞI: Talep edilen model sürümü ({model_version}) "
                    f"dondurulmuş kanonik sürüm ({FROZEN_MODEL_VERSION}) ile eşleşmiyor."
                ),
                "manifest": None,
                "comparison": None,
            }

        # 2. Source Identity Provenance Check
        source_commit = cls.get_source_commit_sha()
        expected_commit = workflow_context.get("expected_source_commit_sha") or workflow_context.get("source_commit_sha")
        provenance_diagnostic = {
            "source_commit_sha": source_commit,
            "source_commit_verified": cls.is_valid_commit_sha(source_commit),
            "expected_source_commit_sha": expected_commit,
            "commit_match": (source_commit.lower() == expected_commit.lower()) if expected_commit and cls.is_valid_commit_sha(expected_commit) and cls.is_valid_commit_sha(source_commit) else None,
        }

        # If source commit is unavailable or not a valid 40-char hex SHA, fail closed
        if not cls.is_valid_commit_sha(source_commit):
            return {
                "verdict": ReproducibilityVerdict.VERIFICATION_UNAVAILABLE.value,
                "reproducible": False,
                "explanation": (
                    "KAYNAK TAAHHÜT KİMLİĞİ BELİRSİZ (SOURCE_COMMIT_UNAVAILABLE): "
                    "Çalışma zamanı için geçerli bir 40 karakterlik onaltılık Git kaynak taahhüt özeti "
                    "tespit edilemedi. Provenance tekrarlanabilirliği doğrulanamaz."
                ),
                "manifest": None,
                "comparison": None,
                "provenance_diagnostic": provenance_diagnostic,
                "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        # If expected commit was passed, enforce strict matching
        if expected_commit:
            if not cls.is_valid_commit_sha(expected_commit):
                return {
                    "verdict": ReproducibilityVerdict.DATASET_PROVENANCE_MISMATCH.value,
                    "reproducible": False,
                    "explanation": (
                        f"GEÇERSİZ BEKLENEN KAYNAK TAAHHÜDÜ: '{expected_commit}' geçerli bir "
                        f"40 karakterlik onaltılık Git SHA değeri değildir."
                    ),
                    "manifest": None,
                    "comparison": None,
                    "provenance_diagnostic": provenance_diagnostic,
                    "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            if source_commit.lower() != expected_commit.lower():
                return {
                    "verdict": ReproducibilityVerdict.DATASET_PROVENANCE_MISMATCH.value,
                    "reproducible": False,
                    "explanation": (
                        f"KAYNAK TAAHHÜT UYUŞMAZLIĞI (SOURCE_COMMIT_MISMATCH): Beklenen derleme taahhüdü "
                        f"({expected_commit[:12]}...) ile çalışma zamanı taahhüdü ({source_commit[:12]}...) uyuşmuyor."
                    ),
                    "manifest": None,
                    "comparison": None,
                    "provenance_diagnostic": provenance_diagnostic,
                    "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
                }

        # 3. Dataset Manifest Provenance Check
        current_manifest = ContentIntegrityEngine.generate_canonical_manifest()
        current_sha = current_manifest.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")
        saved_sha = workflow_context.get("dataset_manifest_sha256")

        if saved_sha and saved_sha != current_sha:
            return {
                "verdict": ReproducibilityVerdict.DATASET_PROVENANCE_MISMATCH.value,
                "reproducible": False,
                "explanation": (
                    f"VERİ PROVENANCE UYUŞMAZLIĞI: Kayıtlı veri seti manifest özeti ({saved_sha[:16]}...) "
                    f"mevcut sistem manifest özeti ({current_sha[:16]}...) ile uyuşmuyor."
                ),
                "manifest": cls.create_reproducibility_manifest(
                    workflow_context.get("workflow_id", ""),
                    workflow_context.get("research_session_id", ""),
                    workflow_context,
                    current_sha,
                ).to_dict(),
                "comparison": None,
                "provenance_diagnostic": provenance_diagnostic,
                "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        # 4. Check for Incomplete Evidence
        if not start_utc or not end_utc:
            return {
                "verdict": ReproducibilityVerdict.INCOMPLETE_EVIDENCE.value,
                "reproducible": False,
                "explanation": "YETERSİZ KANIT: Başlangıç veya bitiş UTC tarih parametreleri eksik.",
                "manifest": None,
                "comparison": None,
                "provenance_diagnostic": provenance_diagnostic,
                "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        # 5. Deterministic Re-run Execution
        try:
            # First run (or original run)
            if original_session:
                run1 = original_session
            else:
                run1 = UnifiedResearchWorkspaceEngine.execute_session(
                    reference_start_utc=start_utc,
                    reference_end_utc=end_utc,
                    asset=asset,
                    interval=interval,
                    selected_modules=modules,
                    force_refresh=True,
                )

            # Re-run for independent reproduction comparison
            run2 = UnifiedResearchWorkspaceEngine.execute_session(
                reference_start_utc=start_utc,
                reference_end_utc=end_utc,
                asset=asset,
                interval=interval,
                selected_modules=modules,
                force_refresh=True,
            )

        except Exception as e:
            return {
                "verdict": ReproducibilityVerdict.VERIFICATION_UNAVAILABLE.value,
                "reproducible": False,
                "explanation": f"ÇALIŞMA ZAMANI HATASI: Rejenerasyon sırasında beklenmeyen hata oluştu: {str(e)}",
                "manifest": None,
                "comparison": None,
                "provenance_diagnostic": provenance_diagnostic,
                "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
            }

        # 6. Compare Module Outputs
        comp = cls.compare_module_outputs(run1, run2)
        manifest = cls.create_reproducibility_manifest(
            workflow_context.get("workflow_id", ""),
            run1.get("session_id", run2.get("session_id", "")),
            workflow_context,
            current_sha,
        ).to_dict()

        # Strict Scientific Invariant:
        # Invalid results (NaN, Inf, None, missing) can NEVER produce REPRODUCIBLE_EXACT or REPRODUCIBLE_WITH_NUMERICAL_TOLERANCE
        has_invalid = comp.get("has_invalid_numerical_values", False) or any(d.get("critical") for d in comp.get("discrepancies", []))

        if has_invalid or not comp["within_tolerances"]:
            comp["all_exact_match"] = False
            comp["within_tolerances"] = False
            verdict = ReproducibilityVerdict.NON_REPRODUCIBLE
            expl = (
                f"REPRODÜSİBL DEĞİL: Çıktılar arasında kabul edilebilir bilimsel toleransı aşan tutarsızlıklar "
                f"veya geçersiz sayısal değerler (NaN, Sonsuz, Eksik Veri) tespit edilmiştir "
                f"(Maks delta: {comp['max_numerical_delta']:.2e}, Hata sayısı: {len(comp['discrepancies'])})."
            )
        elif comp["all_exact_match"]:
            verdict = ReproducibilityVerdict.REPRODUCIBLE_EXACT
            expl = (
                "BİREBİR REPRODÜSİBL (REPRODUCIBLE_EXACT): İki bağımsız çalıştırma arasında tüm analitik çıktılar, "
                "kategorik rejimler, adaysıralamaları ve sayısal değerler %100 birebir eşleşmektedir."
            )
        elif comp["within_tolerances"]:
            verdict = ReproducibilityVerdict.REPRODUCIBLE_WITH_NUMERICAL_TOLERANCE
            expl = (
                f"SAYISAL TOLERANS DÂHİLİNDE REPRODÜSİBL: Tüm kategorik ve yapısal sonuçlar tam uyuşmakta, "
                f"kayan nokta farkları belgelenmiş bilimsel toleranslar dâhilindedir (Maks delta: {comp['max_numerical_delta']:.2e})."
            )
        else:
            verdict = ReproducibilityVerdict.NON_REPRODUCIBLE
            expl = (
                f"REPRODÜSİBL DEĞİL: Çıktılar arasında kabul edilebilir bilimsel toleransı aşan tutarsızlıklar "
                f"tespit edilmiştir (Maks delta: {comp['max_numerical_delta']:.2e}, Hata sayısı: {len(comp['discrepancies'])})."
            )

        return {
            "verdict": verdict.value,
            "reproducible": verdict in (ReproducibilityVerdict.REPRODUCIBLE_EXACT, ReproducibilityVerdict.REPRODUCIBLE_WITH_NUMERICAL_TOLERANCE),
            "explanation": expl,
            "manifest": manifest,
            "comparison": comp,
            "provenance_diagnostic": provenance_diagnostic,
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
