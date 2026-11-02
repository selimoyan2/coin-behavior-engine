"""
CBE — Research Performance Audit & Regression Observatory (Sprint 21)
Measures latency, memory usage, and execution characteristics of historical research engines.
Detects performance regressions against established baseline thresholds.

Operational Safeguards:
1. Explicit operator invocation only — ZERO unattended background monitoring.
2. Bounded execution limits and sample sizes.
3. Disabled in production unless explicitly authorized.
4. ZERO live network market collection or trading execution.
"""

from __future__ import annotations

import gc
import logging
import os
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.historical_pattern_discovery import HistoricalPatternDiscoveryEngine
from coin_behavior_engine.product.research_evidence_verifier import ResearchEvidenceVerifier
from coin_behavior_engine.product.research_intelligence_explorer import (
    ResearchIntelligenceExplorerEngine,
    ResearchLibraryEngine,
)
from coin_behavior_engine.product.research_reproducibility import ResearchReproducibilityEngine
from coin_behavior_engine.product.research_workflow import ResearchWorkflowEngine
from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

logger = logging.getLogger("cbe.research_performance_audit")

# Established performance baseline thresholds (milliseconds)
DEFAULT_LATENCY_THRESHOLDS_MS = {
    "historical_candles_load": 500.0,
    "unified_research_session": 3500.0,
    "pattern_discovery": 2500.0,
    "comparison_studio": 1000.0,
    "evidence_export": 300.0,
    "evidence_verification": 150.0,
    "reproducibility_verification": 5000.0,
    "library_save_reopen": 200.0,
}


class PerformanceSeverity(str, Enum):
    """Performance evaluation severity classification."""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    REGRESSION_WARNING = "REGRESSION_WARNING"
    CRITICAL_REGRESSION = "CRITICAL_REGRESSION"


@dataclass
class BenchmarkMetric:
    """Benchmark measurement for an analytical research operation."""
    operation_name: str
    display_title_tr: str
    latency_ms: float
    threshold_ms: float
    severity: str
    relative_ratio: float
    memory_peak_kb: float
    status: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceAuditReport:
    """Consolidated performance regression observatory report."""
    audit_id: str
    timestamp_utc: str
    overall_status: str
    total_duration_ms: float
    peak_memory_kb: float
    operations_measured: int
    regressions_detected: int
    metrics: Dict[str, BenchmarkMetric] = field(default_factory=dict)
    summary_tr: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "total_duration_ms": self.total_duration_ms,
            "peak_memory_kb": self.peak_memory_kb,
            "operations_measured": self.operations_measured,
            "regressions_detected": self.regressions_detected,
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "summary_tr": self.summary_tr,
        }


class ResearchPerformanceAuditEngine:
    """
    Executes controlled, bounded performance benchmarks across all research components.
    """

    @classmethod
    def run_benchmark_suite(
        cls,
        sample_start_utc: str = "2022-06-01T00:00:00Z",
        sample_end_utc: str = "2022-06-15T00:00:00Z",
        threshold_overrides: Optional[Dict[str, float]] = None,
    ) -> PerformanceAuditReport:
        """
        Execute comprehensive latency and memory benchmarks under controlled conditions.
        """
        thresholds = dict(DEFAULT_LATENCY_THRESHOLDS_MS)
        if threshold_overrides:
            thresholds.update(threshold_overrides)

        metrics: Dict[str, BenchmarkMetric] = {}
        regressions_count = 0
        total_start = time.perf_counter()

        tracemalloc.start()
        initial_mem = tracemalloc.get_traced_memory()[0]

        try:
            # 1. Benchmark Historical Candles Loading
            t0 = time.perf_counter()
            candles_res = ResearchIntelligenceExplorerEngine.get_historical_series(
                start_utc=sample_start_utc,
                end_utc=sample_end_utc,
                asset="BTCUSDT",
                interval="1h",
            )
            lat_candles = (time.perf_counter() - t0) * 1000.0
            cur_mem, peak_mem = tracemalloc.get_traced_memory()
            metrics["historical_candles_load"] = cls._evaluate_metric(
                "historical_candles_load",
                "Tarihsel Mum Verisi Yükleme",
                lat_candles,
                thresholds["historical_candles_load"],
                (peak_mem - initial_mem) / 1024.0,
                {"candles_returned": len(candles_res.get("candles", []))},
            )

            # 2. Benchmark Unified Research Session
            t0 = time.perf_counter()
            sess_data = UnifiedResearchWorkspaceEngine.execute_session(
                asset="BTCUSDT",
                interval="1h",
                reference_start_utc=sample_start_utc,
                reference_end_utc=sample_end_utc,
                selected_modules=["regime_analysis", "volatility_analysis"],
                force_refresh=True,
            )
            lat_sess = (time.perf_counter() - t0) * 1000.0
            metrics["unified_research_session"] = cls._evaluate_metric(
                "unified_research_session",
                "Birleşik Araştırma Oturumu Yürütme (Modüller)",
                lat_sess,
                thresholds["unified_research_session"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"session_success": bool(sess_data)},
            )

            # 3. Benchmark Pattern Discovery Search
            t0 = time.perf_counter()
            pat_res = HistoricalPatternDiscoveryEngine.search_similar_patterns(
                reference_start_utc=sample_start_utc,
                reference_end_utc=sample_end_utc,
                asset="BTCUSDT",
                interval="1h",
                max_candidates=5,
            )
            lat_pat = (time.perf_counter() - t0) * 1000.0
            metrics["pattern_discovery"] = cls._evaluate_metric(
                "pattern_discovery",
                "Tarihsel Örüntü Arama (5D V2)",
                lat_pat,
                thresholds["pattern_discovery"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"candidates_found": len(pat_res.candidates) if pat_res else 0},
            )

            # 4. Benchmark Comparison Studio
            candidate_start = "2024-07-27T01:00:00Z"
            candidate_end = "2024-08-10T01:00:00Z"
            t0 = time.perf_counter()
            comp_res = ResearchIntelligenceExplorerEngine.get_comparison_series(
                start_utc_a=sample_start_utc,
                end_utc_a=sample_end_utc,
                start_utc_b=candidate_start,
                end_utc_b=candidate_end,
                asset="BTCUSDT",
                interval="1h",
            )
            lat_comp = (time.perf_counter() - t0) * 1000.0
            metrics["comparison_studio"] = cls._evaluate_metric(
                "comparison_studio",
                "Karşılaştırma Stüdyosu Çift Periyot Analizi",
                lat_comp,
                thresholds["comparison_studio"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"comparison_valid": comp_res.get("valid", True)},
            )

            # 5. Benchmark Evidence Package Export
            sample_ctx = {
                "workflow_id": "RWF-perf-test-01",
                "research_session_id": "URS-perf-test-01",
                "reference_start_utc": sample_start_utc,
                "reference_end_utc": sample_end_utc,
                "asset": "BTCUSDT",
                "interval": "1h",
                "selected_modules": ["regime_analysis", "volatility_analysis"],
            }
            t0 = time.perf_counter()
            ok_exp, exp_data, _ = ResearchWorkflowEngine.export_workflow_evidence(sample_ctx)
            lat_exp = (time.perf_counter() - t0) * 1000.0
            pkg = exp_data.get("evidence_package", {})
            metrics["evidence_export"] = cls._evaluate_metric(
                "evidence_export",
                "Kanonik Kanıt Paketi Dışa Aktarma & SHA-256",
                lat_exp,
                thresholds["evidence_export"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"export_success": ok_exp},
            )

            # 6. Benchmark Independent Evidence Verification
            t0 = time.perf_counter()
            ver_rep = ResearchEvidenceVerifier.verify_package(pkg)
            lat_ver = (time.perf_counter() - t0) * 1000.0
            metrics["evidence_verification"] = cls._evaluate_metric(
                "evidence_verification",
                "Bağımsız Kanıt Doğrulama & Bütünlük Denetimi",
                lat_ver,
                thresholds["evidence_verification"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"verification_valid": ver_rep.is_valid},
            )

            # 7. Benchmark Reproducibility Verification
            t0 = time.perf_counter()
            repro_res = ResearchReproducibilityEngine.verify_reproducibility(sample_ctx, sess_data)
            lat_repro = (time.perf_counter() - t0) * 1000.0
            metrics["reproducibility_verification"] = cls._evaluate_metric(
                "reproducibility_verification",
                "Tekrarlanabilirlik & Deterministik Çıktı Karşılaştırma",
                lat_repro,
                thresholds["reproducibility_verification"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"verdict": repro_res.get("verdict")},
            )

            # 8. Benchmark Research Library Save & Reopen
            t0 = time.perf_counter()
            save_payload = {
                "title": "Perf Audit Benchmark Run",
                "description": "Transient record for latency measurement",
                "asset": "BTCUSDT",
                "interval": "1h",
                "reference_start_utc": sample_start_utc,
                "reference_end_utc": sample_end_utc,
                "selected_modules": ["regime_analysis"],
                "metadata": {"test_marker": True},
            }
            saved_def = ResearchLibraryEngine.save_definition(save_payload)
            rid = saved_def["research_id"]
            retrieved_def = ResearchLibraryEngine.get_definition(rid)
            ResearchLibraryEngine.delete_definition(rid)
            lat_lib = (time.perf_counter() - t0) * 1000.0
            metrics["library_save_reopen"] = cls._evaluate_metric(
                "library_save_reopen",
                "Araştırma Kütüphanesi Kaydet/Aç/Sil Döngüsü",
                lat_lib,
                thresholds["library_save_reopen"],
                (tracemalloc.get_traced_memory()[1] - initial_mem) / 1024.0,
                {"record_id": rid},
            )

        finally:
            final_mem, peak_all = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            gc.collect()

        total_duration = (time.perf_counter() - total_start) * 1000.0

        # Assess overall regressions
        for m in metrics.values():
            if m.severity in (PerformanceSeverity.REGRESSION_WARNING.value, PerformanceSeverity.CRITICAL_REGRESSION.value):
                regressions_count += 1

        overall_status = "REGRESSION_DETECTED" if regressions_count > 0 else "OPTIMAL"
        summary_tr = (
            f"PERFORMANS GÖZLEMEVİ TAMAMLANDI: Toplam {len(metrics)} operasyon test edildi. "
            f"Toplam süre: {total_duration:.1f}ms, Tepe bellek: {peak_all / 1024.0:.1f} KB. "
            f"Tespit edilen regresyon: {regressions_count}."
        )

        audit_id = f"PRF-{int(time.time())}"

        return PerformanceAuditReport(
            audit_id=audit_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            overall_status=overall_status,
            total_duration_ms=round(total_duration, 2),
            peak_memory_kb=round(peak_all / 1024.0, 2),
            operations_measured=len(metrics),
            regressions_detected=regressions_count,
            metrics=metrics,
            summary_tr=summary_tr,
        )

    @classmethod
    def _evaluate_metric(
        cls,
        op_name: str,
        title_tr: str,
        latency_ms: float,
        threshold_ms: float,
        mem_peak_kb: float,
        details: Dict[str, Any],
    ) -> BenchmarkMetric:
        ratio = latency_ms / threshold_ms if threshold_ms > 0 else 1.0

        if ratio <= 0.8:
            sev = PerformanceSeverity.NORMAL
            status = "PASS"
        elif ratio <= 1.0:
            sev = PerformanceSeverity.ELEVATED
            status = "PASS"
        elif ratio <= 1.5:
            sev = PerformanceSeverity.REGRESSION_WARNING
            status = "WARNING"
        else:
            sev = PerformanceSeverity.CRITICAL_REGRESSION
            status = "FAIL"

        return BenchmarkMetric(
            operation_name=op_name,
            display_title_tr=title_tr,
            latency_ms=round(latency_ms, 2),
            threshold_ms=round(threshold_ms, 2),
            severity=sev.value,
            relative_ratio=round(ratio, 3),
            memory_peak_kb=round(mem_peak_kb, 2),
            status=status,
            details=details,
        )
