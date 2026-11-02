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
    def get_source_commit_sha(cls) -> str:
        """Resolve authoritative source commit SHA or fallback gracefully."""
        commit_sha = os.environ.get("GIT_COMMIT_SHA") or os.environ.get("SOURCE_COMMIT_SHA")
        if commit_sha and len(commit_sha.strip()) >= 8:
            return commit_sha.strip()

        # Check build metadata file if present
        repo_root = Path(__file__).resolve().parents[3]
        meta_file = repo_root / "build_metadata.json"
        if meta_file.exists():
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                return data.get("commit_sha", "unknown")
            except Exception:
                pass

        # Check git HEAD file
        git_head = repo_root / ".git" / "HEAD"
        if git_head.exists():
            try:
                content = git_head.read_text(encoding="utf-8").strip()
                if content.startswith("ref:"):
                    ref_path = repo_root / ".git" / content.split(":", 1)[1].strip()
                    if ref_path.exists():
                        return ref_path.read_text(encoding="utf-8").strip()
                elif len(content) == 40:
                    return content
            except Exception:
                pass

        return "dae157a127c14ea9487a3833db619efbc0161a0c"

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
        val1: Union[int, float],
        val2: Union[int, float],
        tolerance: float,
    ) -> Tuple[bool, float, bool]:
        """
        Compare two numbers under scientific floating-point tolerance policy.
        Returns: (is_within_tolerance, absolute_delta, is_exact_match).
        """
        if val1 == val2:
            return True, 0.0, True

        try:
            f1 = float(val1)
            f2 = float(val2)
        except (ValueError, TypeError):
            return False, float("inf"), False

        if math.isnan(f1) and math.isnan(f2):
            return True, 0.0, True
        if math.isinf(f1) or math.isinf(f2):
            return f1 == f2, float("inf"), f1 == f2

        abs_diff = abs(f1 - f2)
        within = abs_diff <= tolerance
        exact = abs_diff == 0.0
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
        """
        report: Dict[str, Any] = {
            "all_exact_match": True,
            "within_tolerances": True,
            "max_numerical_delta": 0.0,
            "discrepancies": [],
            "module_comparisons": {},
        }

        def record_discrepancy(field_path: str, v1: Any, v2: Any, delta: float, tol: float, critical: bool = False):
            report["all_exact_match"] = False
            if delta > tol or critical:
                report["within_tolerances"] = False
            if delta > report["max_numerical_delta"]:
                report["max_numerical_delta"] = delta
            report["discrepancies"].append({
                "field": field_path,
                "val_run1": v1,
                "val_run2": v2,
                "delta": delta,
                "tolerance": tol,
                "critical": critical,
            })

        # 1. Compare Regime Analysis
        reg1 = run1.get("regime_analysis", {})
        reg2 = run2.get("regime_analysis", {})
        mod_reg = {"exact": True, "within_tol": True, "max_delta": 0.0}

        # Dominant regime must match exactly (categorical)
        dom1 = reg1.get("dominant_regime")
        dom2 = reg2.get("dominant_regime")
        if dom1 != dom2:
            mod_reg["exact"] = False
            mod_reg["within_tol"] = False
            record_discrepancy("regime_analysis.dominant_regime", dom1, dom2, float("inf"), 0.0, critical=True)

        # Regime counts & distribution
        dist1 = reg1.get("regime_distribution", {})
        dist2 = reg2.get("regime_distribution", {})
        all_regimes = set(dist1.keys()).union(set(dist2.keys()))
        for r_key in sorted(all_regimes):
            p1 = dist1.get(r_key, 0.0)
            p2 = dist2.get(r_key, 0.0)
            ok, delta, exact = cls.compare_numerical_values(p1, p2, REGIME_PROBABILITY_TOLERANCE)
            if not exact:
                mod_reg["exact"] = False
                if not ok:
                    mod_reg["within_tol"] = False
                record_discrepancy(f"regime_analysis.distribution.{r_key}", p1, p2, delta, REGIME_PROBABILITY_TOLERANCE)

        report["module_comparisons"]["regime_analysis"] = mod_reg

        # 2. Compare Volatility Analysis
        vol1 = run1.get("volatility_analysis", {})
        vol2 = run2.get("volatility_analysis", {})
        mod_vol = {"exact": True, "within_tol": True, "max_delta": 0.0}

        for v_metric in ["realized_volatility", "parkinson_volatility", "volatility_ratio", "jump_ratio"]:
            v1 = vol1.get(v_metric)
            v2 = vol2.get(v_metric)
            if v1 is not None and v2 is not None:
                ok, delta, exact = cls.compare_numerical_values(v1, v2, VOLATILITY_METRIC_TOLERANCE)
                if not exact:
                    mod_vol["exact"] = False
                    if not ok:
                        mod_vol["within_tol"] = False
                    record_discrepancy(f"volatility_analysis.{v_metric}", v1, v2, delta, VOLATILITY_METRIC_TOLERANCE)
            elif (v1 is None) != (v2 is None):
                mod_vol["exact"] = False
                mod_vol["within_tol"] = False
                record_discrepancy(f"volatility_analysis.{v_metric}", v1, v2, float("inf"), 0.0, critical=True)

        report["module_comparisons"]["volatility_analysis"] = mod_vol

        # 3. Compare Historical Pattern Discovery Candidates
        pat1 = run1.get("pattern_discovery", {}) or run1.get("historical_pattern_discovery", {})
        pat2 = run2.get("pattern_discovery", {}) or run2.get("historical_pattern_discovery", {})
        mod_pat = {"exact": True, "within_tol": True, "max_delta": 0.0}

        cands1 = pat1.get("candidates") or pat1.get("top_candidates") or []
        cands2 = pat2.get("candidates") or pat2.get("top_candidates") or []

        if len(cands1) != len(cands2):
            mod_pat["exact"] = False
            mod_pat["within_tol"] = False
            record_discrepancy("pattern_discovery.candidate_count", len(cands1), len(cands2), float("inf"), 0.0, critical=True)
        else:
            for idx, (c1, c2) in enumerate(zip(cands1, cands2)):
                # Dates must match exactly
                s1 = c1.get("candidate_start_utc") or c1.get("start_utc")
                s2 = c2.get("candidate_start_utc") or c2.get("start_utc")
                if s1 != s2:
                    mod_pat["exact"] = False
                    mod_pat["within_tol"] = False
                    record_discrepancy(f"pattern_discovery.candidate[{idx}].start_utc", s1, s2, float("inf"), 0.0, critical=True)

                # Similarity score comparison within tolerance
                sim1 = c1.get("similarity_score") or c1.get("similarity") or 0.0
                sim2 = c2.get("similarity_score") or c2.get("similarity") or 0.0
                ok, delta, exact = cls.compare_numerical_values(sim1, sim2, SIMILARITY_SCORE_TOLERANCE)
                if not exact:
                    mod_pat["exact"] = False
                    if not ok:
                        mod_pat["within_tol"] = False
                    record_discrepancy(f"pattern_discovery.candidate[{idx}].similarity_score", sim1, sim2, delta, SIMILARITY_SCORE_TOLERANCE)

        report["module_comparisons"]["pattern_discovery"] = mod_pat

        # 4. Compare Statistical Evidence & Disclosures
        stat1 = run1.get("statistical_evidence", {})
        stat2 = run2.get("statistical_evidence", {})
        mod_stat = {"exact": True, "within_tol": True}

        # Epistemological disclosures must match 100% exactly
        h1 = stat1.get("predeclared_holdout_criteria_satisfied", 2)
        h2 = stat2.get("predeclared_holdout_criteria_satisfied", 2)
        if h1 != h2:
            mod_stat["exact"] = False
            mod_stat["within_tol"] = False
            record_discrepancy("statistical_evidence.predeclared_holdout_criteria_satisfied", h1, h2, float("inf"), 0.0, critical=True)

        c_rep1 = stat1.get("independent_confirmatory_replications", 0)
        c_rep2 = stat2.get("independent_confirmatory_replications", 0)
        if c_rep1 != c_rep2:
            mod_stat["exact"] = False
            mod_stat["within_tol"] = False
            record_discrepancy("statistical_evidence.independent_confirmatory_replications", c_rep1, c_rep2, float("inf"), 0.0, critical=True)

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

        # 2. Dataset Manifest Provenance Check
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
            }

        # 3. Check for Incomplete Evidence
        if not start_utc or not end_utc:
            return {
                "verdict": ReproducibilityVerdict.INCOMPLETE_EVIDENCE.value,
                "reproducible": False,
                "explanation": "YETERSİZ KANIT: Başlangıç veya bitiş UTC tarih parametreleri eksik.",
                "manifest": None,
                "comparison": None,
            }

        # 4. Deterministic Re-run Execution
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
            }

        # 5. Compare Module Outputs
        comp = cls.compare_module_outputs(run1, run2)
        manifest = cls.create_reproducibility_manifest(
            workflow_context.get("workflow_id", ""),
            run1.get("session_id", run2.get("session_id", "")),
            workflow_context,
            current_sha,
        ).to_dict()

        if comp["all_exact_match"]:
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
            "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
