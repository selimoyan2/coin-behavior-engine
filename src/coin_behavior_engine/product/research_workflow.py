"""
Sprint Product Acceleration 20 — Unified Research Workflow & Product Experience V1.

Implements a lightweight workflow orchestration layer that coordinates existing CBE
research modules without reimplementing their analytical algorithms:
- Research Intelligence Explorer V1
- Unified Research Workspace V1
- Historical Pattern Discovery V2
- Comparison Studio V2
- Research Library V2
- Unified Evidence Package Export

Safety and Governance Invariants:
1. Canonical Model: CBE-0.7.0 (STRICTLY FROZEN — ZERO PARAMETER MUTATIONS).
2. Purely retrospective, historical, and descriptive research.
3. ZERO live order execution, ZERO directional trading signals, ZERO profit claims.
4. Quarantine enforcement: October 2026 partitions strictly excluded.
5. Epistemological disclosure: Holdout previously exposed, exploratory holdout satisfaction
   is NOT independent confirmatory replication. (2 satisfied, 0 independent confirmatory).
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.historical_pattern_discovery import (
    HistoricalPatternDiscoveryEngine,
    PatternDiscoverySearchResult,
)
from coin_behavior_engine.product.research_intelligence_explorer import (
    ResearchIntelligenceExplorerEngine,
    ResearchLibraryEngine,
)
from coin_behavior_engine.product.unified_research_workspace import (
    UnifiedResearchWorkspaceEngine,
    UnifiedResearchSession,
)

logger = logging.getLogger("cbe_research_workflow")

SAFE_WORKFLOW_ID_REGEX = re.compile(r"^RWF-[a-f0-9]{16}$")
OCTOBER_2026_QUARANTINE_START = "2026-10-01T00:00:00Z"


class WorkflowStage(str, Enum):
    """Canonical finite state machine stages for the research journey."""
    INITIAL = "INITIAL"
    PERIOD_SELECTED = "PERIOD_SELECTED"
    SESSION_READY = "SESSION_READY"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    PATTERNS_REVIEWED = "PATTERNS_REVIEWED"
    COMPARISON_READY = "COMPARISON_READY"
    RESEARCH_SAVED = "RESEARCH_SAVED"
    EVIDENCE_EXPORTED = "EVIDENCE_EXPORTED"


# Valid forward and backward transitions
ALLOWED_STAGE_TRANSITIONS: Dict[WorkflowStage, List[WorkflowStage]] = {
    WorkflowStage.INITIAL: [WorkflowStage.PERIOD_SELECTED],
    WorkflowStage.PERIOD_SELECTED: [WorkflowStage.INITIAL, WorkflowStage.SESSION_READY],
    WorkflowStage.SESSION_READY: [WorkflowStage.PERIOD_SELECTED, WorkflowStage.ANALYSIS_COMPLETED],
    WorkflowStage.ANALYSIS_COMPLETED: [
        WorkflowStage.PERIOD_SELECTED,
        WorkflowStage.SESSION_READY,
        WorkflowStage.PATTERNS_REVIEWED,
        WorkflowStage.RESEARCH_SAVED,
        WorkflowStage.EVIDENCE_EXPORTED,
    ],
    WorkflowStage.PATTERNS_REVIEWED: [
        WorkflowStage.ANALYSIS_COMPLETED,
        WorkflowStage.COMPARISON_READY,
        WorkflowStage.RESEARCH_SAVED,
        WorkflowStage.EVIDENCE_EXPORTED,
    ],
    WorkflowStage.COMPARISON_READY: [
        WorkflowStage.PATTERNS_REVIEWED,
        WorkflowStage.ANALYSIS_COMPLETED,
        WorkflowStage.RESEARCH_SAVED,
        WorkflowStage.EVIDENCE_EXPORTED,
    ],
    WorkflowStage.RESEARCH_SAVED: [
        WorkflowStage.ANALYSIS_COMPLETED,
        WorkflowStage.COMPARISON_READY,
        WorkflowStage.EVIDENCE_EXPORTED,
    ],
    WorkflowStage.EVIDENCE_EXPORTED: [
        WorkflowStage.INITIAL,
        WorkflowStage.PERIOD_SELECTED,
        WorkflowStage.ANALYSIS_COMPLETED,
        WorkflowStage.RESEARCH_SAVED,
    ],
}


@dataclass
class SharedResearchContext:
    """
    Canonical shared research context contract synchronized across all CBE research modules.
    Guarantees that no module operates on disjoint or stale parameter sets.
    """
    schema_version: str = "1.0.0"
    workflow_id: str = ""
    stage: str = WorkflowStage.INITIAL.value
    asset: str = "BTCUSDT"
    interval: str = "1h"
    reference_start_utc: str = ""
    reference_end_utc: str = ""
    selected_modules: List[str] = field(default_factory=lambda: [
        "regime_analysis",
        "volatility_analysis",
        "historical_pattern_discovery",
        "macro_comparison",
        "statistical_evidence",
    ])
    research_session_id: Optional[str] = None
    pattern_experiment_id: Optional[str] = None
    comparison_reference: Optional[Dict[str, Any]] = None
    research_library_id: Optional[str] = None
    dataset_manifest_sha256: str = ""
    canonical_model_version: str = FROZEN_MODEL_VERSION
    research_only: bool = True
    context_version: int = 1
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchWorkflowEngine:
    """
    Coordinates historical market exploration, unified research sessions,
    pattern discovery, episode comparison, library persistence, and evidence export.
    """

    _WORKFLOW_CACHE: Dict[str, Dict[str, Any]] = {}
    _MAX_CACHE_ENTRIES = 50

    @classmethod
    def generate_workflow_id(
        cls,
        asset: str,
        interval: str,
        start_utc: str,
        end_utc: str,
        selected_modules: List[str],
        manifest_hash: str = "",
    ) -> str:
        """
        Derive deterministic workflow identifier from stable research parameters and dataset provenance.
        Volatile execution timestamps or tokens are strictly excluded.
        """
        norm_modules = sorted([str(m).strip().lower() for m in selected_modules])
        fingerprint_obj = {
            "canonical_model": FROZEN_MODEL_VERSION,
            "asset": asset.strip().upper(),
            "interval": interval.strip().lower(),
            "start_utc": start_utc.strip(),
            "end_utc": end_utc.strip(),
            "selected_modules": norm_modules,
            "manifest_sha256": manifest_hash.strip(),
        }
        raw_bytes = json.dumps(fingerprint_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        h = hashlib.sha256(raw_bytes).hexdigest()[:16]
        return f"RWF-{h}"

    @classmethod
    def validate_historical_period(cls, start_utc: str, end_utc: str) -> Tuple[bool, Optional[str]]:
        """Validate date-range format, order, and strict quarantine boundary."""
        if not start_utc or not end_utc:
            return False, "Eksik parametre: 'start_utc' ve 'end_utc' zorunludur."

        try:
            dt_start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
            dt_end = datetime.fromisoformat(end_utc.replace("Z", "+00:00"))
        except Exception as e:
            return False, f"Geçersiz ISO 8601 tarih formatı: {e}"

        if dt_start >= dt_end:
            return False, "Tarih aralığı hatası: 'start_utc', 'end_utc' değerinden önce olmalıdır."

        # Quarantine check
        dt_quarantine = datetime.fromisoformat(OCTOBER_2026_QUARANTINE_START.replace("Z", "+00:00"))
        if dt_start >= dt_quarantine or dt_end > dt_quarantine:
            return False, (
                "KARANTİNA İHLALİ: Ekim 2026 ve sonrası ileriye dönük gözlem periyodudur. "
                "Geçmişe dönük (retrospektif) araştırmalar için Eylül 2026 ve öncesi kullanılmalıdır."
            )

        return True, None

    @classmethod
    def create_or_update_workflow(
        cls,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        start_utc: str = "",
        end_utc: str = "",
        selected_modules: Optional[List[str]] = None,
        target_stage: Optional[WorkflowStage] = None,
        existing_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Initialize or transition a research workflow instance, maintaining state invariants.
        """
        modules = selected_modules or [
            "regime_analysis",
            "volatility_analysis",
            "historical_pattern_discovery",
            "macro_comparison",
            "statistical_evidence",
        ]

        # Dataset manifest provenance check
        manifest_meta = ContentIntegrityEngine.generate_canonical_manifest()
        manifest_sha = manifest_meta.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")

        is_valid_period = False
        if start_utc and end_utc:
            valid, err = cls.validate_historical_period(start_utc, end_utc)
            if not valid:
                return False, {}, err
            is_valid_period = True

        workflow_id = cls.generate_workflow_id(
            asset=asset,
            interval=interval,
            start_utc=start_utc,
            end_utc=end_utc,
            selected_modules=modules,
            manifest_hash=manifest_sha,
        )

        # Detect stale results or date invalidation
        context = copy.deepcopy(existing_context) if existing_context else {}
        context_ver = context.get("context_version", 0) + 1

        prev_start = context.get("reference_start_utc", "")
        prev_end = context.get("reference_end_utc", "")
        range_changed = (prev_start and prev_start != start_utc) or (prev_end and prev_end != end_utc)

        # Invalidate dependent session/comparison IDs if date range changed
        session_id = None if range_changed else context.get("research_session_id")
        experiment_id = None if range_changed else context.get("pattern_experiment_id")
        comparison_ref = None if range_changed else context.get("comparison_reference")

        # Determine stage
        current_stage = WorkflowStage(context.get("stage", WorkflowStage.INITIAL.value))
        if target_stage:
            new_stage = target_stage
        elif range_changed:
            new_stage = WorkflowStage.PERIOD_SELECTED
        elif comparison_ref:
            new_stage = WorkflowStage.COMPARISON_READY
        elif session_id:
            new_stage = WorkflowStage.ANALYSIS_COMPLETED
        elif is_valid_period:
            new_stage = WorkflowStage.PERIOD_SELECTED
        else:
            new_stage = WorkflowStage.INITIAL

        shared_ctx = SharedResearchContext(
            schema_version="1.0.0",
            workflow_id=workflow_id,
            stage=new_stage.value,
            asset=asset,
            interval=interval,
            reference_start_utc=start_utc,
            reference_end_utc=end_utc,
            selected_modules=modules,
            research_session_id=session_id,
            pattern_experiment_id=experiment_id,
            comparison_reference=comparison_ref,
            research_library_id=context.get("research_library_id"),
            dataset_manifest_sha256=manifest_sha,
            canonical_model_version=FROZEN_MODEL_VERSION,
            research_only=True,
            context_version=context_ver,
            created_at_utc=context.get("created_at_utc", datetime.now(timezone.utc).isoformat()),
            updated_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        ctx_dict = shared_ctx.to_dict()

        # Cache management
        if len(cls._WORKFLOW_CACHE) >= cls._MAX_CACHE_ENTRIES:
            oldest_key = next(iter(cls._WORKFLOW_CACHE))
            cls._WORKFLOW_CACHE.pop(oldest_key, None)
        cls._WORKFLOW_CACHE[workflow_id] = ctx_dict

        return True, ctx_dict, None

    @classmethod
    def execute_workflow_session(
        cls,
        context: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Orchestrate Unified Research Session for the shared context via UnifiedResearchWorkspaceEngine.
        Does not duplicate scientific calculations; delegates directly to Sprint 18 engine.
        """
        start_utc = context.get("reference_start_utc")
        end_utc = context.get("reference_end_utc")
        asset = context.get("asset", "BTCUSDT")
        interval = context.get("interval", "1h")
        modules = context.get("selected_modules")

        valid, err = cls.validate_historical_period(start_utc, end_utc)
        if not valid:
            return False, {}, err

        try:
            # Delegate directly to existing UnifiedResearchWorkspaceEngine
            session_obj = UnifiedResearchWorkspaceEngine.execute_session(
                asset=asset,
                interval=interval,
                reference_start_utc=start_utc,
                reference_end_utc=end_utc,
                selected_modules=modules,
            )
            session_data = session_obj if isinstance(session_obj, dict) else session_obj.to_dict()
            session_id = session_data.get("session_id")

            # Extract pattern experiment id if historical pattern discovery succeeded
            exp_id = None
            if "historical_pattern_discovery" in session_data.get("modules", {}):
                mod_pats = session_data["modules"]["historical_pattern_discovery"]
                if mod_pats.get("status") == "SUCCESS":
                    exp_id = mod_pats.get("data", {}).get("experiment_id")

            # Update context
            updated_ctx = copy.deepcopy(context)
            updated_ctx["research_session_id"] = session_id
            updated_ctx["pattern_experiment_id"] = exp_id
            updated_ctx["stage"] = WorkflowStage.ANALYSIS_COMPLETED.value
            updated_ctx["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
            updated_ctx["context_version"] = updated_ctx.get("context_version", 1) + 1

            cls._WORKFLOW_CACHE[updated_ctx["workflow_id"]] = updated_ctx

            return True, {
                "workflow_context": updated_ctx,
                "session": session_data,
                "scientific_explanations": cls.generate_scientific_explanations(session_data),
            }, None
        except Exception as e:
            logger.exception("Failed to execute workflow session: %s", e)
            return False, {}, f"Unified Research Session yürütme hatası: {str(e)}"

    @classmethod
    def select_comparison_candidate(
        cls,
        context: Dict[str, Any],
        candidate_start_utc: str,
        candidate_end_utc: str,
        candidate_label: Optional[str] = None,
        similarity_score: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Record candidate period comparison selection in the shared context.
        Preserves candidate boundaries and similarity metadata without substitution.
        """
        valid, err = cls.validate_historical_period(candidate_start_utc, candidate_end_utc)
        if not valid:
            return False, {}, err

        ref_start = context.get("reference_start_utc")
        ref_end = context.get("reference_end_utc")

        # Disjointness check: candidate must not overlap reference period
        if not (candidate_end_utc <= ref_start or candidate_start_utc >= ref_end):
            return False, {}, (
                "BİLİMSEL KURAL İHLALİ: Karşılaştırma adayı, referans periyot ile çakışamaz "
                "(Disjointness requirement violated)."
            )

        comparison_meta = {
            "candidate_start_utc": candidate_start_utc,
            "candidate_end_utc": candidate_end_utc,
            "candidate_label": candidate_label or f"Aday ({candidate_start_utc[:10]})",
            "similarity_score": similarity_score,
            "selected_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        updated_ctx = copy.deepcopy(context)
        updated_ctx["comparison_reference"] = comparison_meta
        updated_ctx["stage"] = WorkflowStage.COMPARISON_READY.value
        updated_ctx["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        updated_ctx["context_version"] = updated_ctx.get("context_version", 1) + 1

        cls._WORKFLOW_CACHE[updated_ctx["workflow_id"]] = updated_ctx

        return True, updated_ctx, None

    @classmethod
    def save_workflow_to_library(
        cls,
        context: Dict[str, Any],
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Save complete workflow configuration to Research Library V2 with schema validation.
        Does not store raw candle arrays.
        """
        title = title.strip()
        if not title:
            return False, {}, "Başlık zorunludur."

        library_payload = {
            "title": title,
            "description": description,
            "asset": context.get("asset", "BTCUSDT"),
            "interval": context.get("interval", "1h"),
            "reference_start_utc": context.get("reference_start_utc"),
            "reference_end_utc": context.get("reference_end_utc"),
            "tags": tags or ["workflow", context.get("asset", "BTCUSDT").lower()],
            "selected_modules": context.get("selected_modules", []),
            "metadata": {
                "workflow_id": context.get("workflow_id"),
                "research_session_id": context.get("research_session_id"),
                "comparison_reference": context.get("comparison_reference"),
                "dataset_manifest_sha256": context.get("dataset_manifest_sha256"),
                "canonical_model_version": FROZEN_MODEL_VERSION,
            },
        }

        try:
            created_def = ResearchLibraryEngine.save_definition(library_payload)
            rid = created_def["research_id"]

            updated_ctx = copy.deepcopy(context)
            updated_ctx["research_library_id"] = rid
            updated_ctx["stage"] = WorkflowStage.RESEARCH_SAVED.value
            updated_ctx["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
            updated_ctx["context_version"] = updated_ctx.get("context_version", 1) + 1

            cls._WORKFLOW_CACHE[updated_ctx["workflow_id"]] = updated_ctx

            return True, {
                "workflow_context": updated_ctx,
                "library_definition": created_def,
            }, None
        except Exception as e:
            return False, {}, f"Kütüphaneye kaydetme hatası: {str(e)}"

    @classmethod
    def restore_workflow_from_library(
        cls,
        research_id: str,
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Restore full research workflow state from a saved library configuration.
        Checks for dataset manifest mismatches and surfaces warnings if provenance changed.
        """
        definition = ResearchLibraryEngine.get_definition(research_id)
        if not definition:
            return False, {}, f"Kütüphane tanımı bulunamadı: {research_id}"

        # Current manifest check
        current_meta = ContentIntegrityEngine.generate_canonical_manifest()
        current_sha = current_meta.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")

        saved_meta = definition.get("metadata", {})
        saved_sha = saved_meta.get("dataset_manifest_sha256", "")
        provenance_mismatch = bool(saved_sha and saved_sha != current_sha)

        start_utc = definition.get("reference_start_utc", "")
        end_utc = definition.get("reference_end_utc", "")
        asset = definition.get("asset", "BTCUSDT")
        interval = definition.get("interval", "1h")
        modules = definition.get("selected_modules") or [
            "regime_analysis",
            "volatility_analysis",
            "historical_pattern_discovery",
            "macro_comparison",
            "statistical_evidence",
        ]

        workflow_id = cls.generate_workflow_id(
            asset=asset,
            interval=interval,
            start_utc=start_utc,
            end_utc=end_utc,
            selected_modules=modules,
            manifest_hash=current_sha,
        )

        comparison_ref = saved_meta.get("comparison_reference")
        stage = WorkflowStage.COMPARISON_READY if comparison_ref else WorkflowStage.PERIOD_SELECTED

        shared_ctx = SharedResearchContext(
            schema_version="1.0.0",
            workflow_id=workflow_id,
            stage=stage.value,
            asset=asset,
            interval=interval,
            reference_start_utc=start_utc,
            reference_end_utc=end_utc,
            selected_modules=modules,
            research_session_id=saved_meta.get("research_session_id"),
            comparison_reference=comparison_ref,
            research_library_id=research_id,
            dataset_manifest_sha256=current_sha,
            canonical_model_version=FROZEN_MODEL_VERSION,
            research_only=True,
            context_version=1,
        )

        ctx_dict = shared_ctx.to_dict()
        cls._WORKFLOW_CACHE[workflow_id] = ctx_dict

        return True, {
            "workflow_context": ctx_dict,
            "library_definition": definition,
            "provenance_mismatch": provenance_mismatch,
            "saved_manifest_sha256": saved_sha,
            "current_manifest_sha256": current_sha,
            "warning": (
                "VERİ PROVENANCE UYARISI: Veri seti sağlama özeti (manifest hash) değişmiştir. "
                "Sonuçlar orijinal kayıtla birebir örtüşmeyebilir."
                if provenance_mismatch else None
            ),
        }, None

    @classmethod
    def export_workflow_evidence(
        cls,
        context: Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Generate reproducible unified evidence package with canonical SHA-256 checksum.
        Integrates session data, comparison, scientific limitations, and holdout lineage.
        """
        workflow_id = context.get("workflow_id")
        session_id = context.get("research_session_id")
        start_utc = context.get("reference_start_utc")
        end_utc = context.get("reference_end_utc")

        if not start_utc or not end_utc:
            return False, {}, "Araştırma periyodu belirlenmemiş."

        manifest_meta = ContentIntegrityEngine.generate_canonical_manifest()

        evidence_package: Dict[str, Any] = {
            "export_schema_version": "CBE-WORKFLOW-EVIDENCE-1.0.0",
            "workflow_id": workflow_id,
            "research_session_id": session_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "canonical_model": {
                "version": FROZEN_MODEL_VERSION,
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "dataset_provenance": {
                "manifest_sha256": manifest_meta.get("manifest_sha256", ""),
                "quarantine_status": "OCTOBER_2026_EXCLUDED",
            },
            "research_specification": {
                "asset": context.get("asset", "BTCUSDT"),
                "interval": context.get("interval", "1h"),
                "reference_start_utc": start_utc,
                "reference_end_utc": end_utc,
                "selected_modules": context.get("selected_modules", []),
            },
            "comparison_metadata": context.get("comparison_reference"),
            "scientific_disclosures": {
                "predeclared_holdout_criteria_satisfied": 2,
                "independent_confirmatory_replications": 0,
                "holdout_status": (
                    "Eksploratif holdout kriterleri karşılanmış olup, geçmişte açığa çıkarılmış veri "
                    "nedeniyle bağımsız doğrulayıcı replikasyon (confirmatory replication) olarak KABUL EDİLEMEZ."
                ),
                "epistemological_limitations": [
                    "Analizler 100% geriye dönük ve betimseldir.",
                    "Tarihsel benzerlik gelecekteki fiyat hareketlerini garanti etmez.",
                    "Sıfır canlı emir iletimi, sıfır yönlü işlem sinyali, sıfır getiri taahhüdü.",
                ],
            },
        }

        # Canonical SHA-256 Checksum over stable sorted JSON
        raw_bytes = json.dumps(evidence_package, sort_keys=True, separators=(",", ":")).encode("utf-8")
        package_checksum = hashlib.sha256(raw_bytes).hexdigest()
        evidence_package["package_checksum_sha256"] = package_checksum

        # Transition stage to EVIDENCE_EXPORTED
        updated_ctx = copy.deepcopy(context)
        updated_ctx["stage"] = WorkflowStage.EVIDENCE_EXPORTED.value
        updated_ctx["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        cls._WORKFLOW_CACHE[workflow_id] = updated_ctx

        return True, {
            "evidence_package": evidence_package,
            "workflow_context": updated_ctx,
        }, None

    @classmethod
    def generate_scientific_explanations(cls, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce clear, objective, descriptive Turkish scientific explanation cards
        for all active modules without generating speculative predictive claims.
        """
        explanations = {}
        modules = session_data.get("module_results", {}) or session_data.get("modules", {})

        # 1. Regime Analysis Explanation
        if "regime_analysis" in modules and modules["regime_analysis"].get("status") == "SUCCESS":
            reg_data = modules["regime_analysis"].get("data", {})
            dom = reg_data.get("dominant_regime", "NEUTRAL")
            dist = reg_data.get("regime_distribution", {})
            explanations["regime"] = {
                "title": "Piyasa Rejimi Analizi Açıklaması",
                "dominant_regime": dom,
                "summary": (
                    f"İncelenen tarihsel periyotta piyasa en çok '{dom}' rejiminde kalmıştır "
                    f"(%{(dist.get(dom, 0)*100):.1f}). Rejim sürekliliği ve geçiş matrisi, "
                    f"CBE-0.7.0 kural tabanlı durum makinesi tarafından tespit edilmiştir."
                ),
                "limitations": "Rejim sınıflandırması geriye dönük segmentasyondur, gelecekteki kırılımları kestirmez.",
            }

        # 2. Volatility Explanation
        if "volatility_analysis" in modules and modules["volatility_analysis"].get("status") == "SUCCESS":
            vol_data = modules["volatility_analysis"].get("data", {})
            explanations["volatility"] = {
                "title": "Oynaklık (Volatilite) Metrikleri Açıklaması",
                "realized_vol": vol_data.get("realized_volatility_annualized"),
                "parkinson_vol": vol_data.get("parkinson_volatility_annualized"),
                "summary": (
                    "Yüksek-düşük fiyat salınımını ölçen Parkinson oynaklığı ve kapanıştan kapanışa "
                    "gerçekleşen oynaklık normalize edilerek sunulmuştur."
                ),
                "limitations": "Düşük örneklem boyutlu kısa periyotlarda yıllıklandırılmış oynaklık yüksek varyans gösterebilir.",
            }

        # 3. Historical Pattern Similarity Explanation
        if "historical_pattern_discovery" in modules and modules["historical_pattern_discovery"].get("status") == "SUCCESS":
            pat_data = modules["historical_pattern_discovery"].get("data", {})
            top_cand = pat_data.get("candidates", [])[:1]
            top_score = top_cand[0].get("similarity_score") if top_cand else None
            explanations["pattern_similarity"] = {
                "title": "Tarihsel Örüntü Benzerliği Açıklaması",
                "best_similarity": top_score,
                "summary": (
                    f"En yakın tarihsel eşleşme %{((top_score or 0)*100):.1f} benzerlik skoru ile tespit edilmiştir. "
                    "Skor; getiri korelasyonu, oynaklık oranı, rejim uyumu, hacim profili ve şekil mesafesinden oluşan "
                    "5 boyutlu ağırlıklı metriğe dayanır."
                ),
                "limitations": "Tarihsel benzerlik, nedensel veya öngörüsel bir garanti değildir.",
                "disjointness_rule": "Referans periyot ile zamansal çakışması olan adaylar katı şekilde elenmiştir.",
            }

        # 4. Macro Events Explanation
        macro_mod = modules.get("macro_comparison") or modules.get("macro_event_context")
        if macro_mod and macro_mod.get("status") == "SUCCESS":
            macro_data = macro_mod.get("data", {})
            events_in_range = macro_data.get("events_in_range", []) or macro_data.get("events", [])
            events_cnt = len(events_in_range)
            explanations["macro_events"] = {
                "title": "Makro Olay ve Takvim Bağlamı",
                "events_count": events_cnt,
                "summary": (
                    f"Periyot boyunca 238 doğrulanmış kanonik olay kataloğundan {events_cnt} adet makro olay "
                    "(FOMC, TÜFE, regülasyon vb.) zaman çizelgesinde eşleşmiştir."
                ),
                "limitations": "Zamansal yakınlık tek başına nedensellik kanıtı oluşturmaz.",
            }

        # 5. Statistical Evidence & Holdout Lineage
        explanations["statistical_evidence"] = {
            "title": "İstatistiki Kanıt ve Epistemolojik Beyan",
            "predeclared_holdout_criteria_satisfied": 2,
            "independent_confirmatory_replications": 0,
            "fdr_alpha": 0.05,
            "summary": (
                "Model kanonik CBE-0.7.0 olup 0 parametre mutasyonuna sahiptir. Önceden belirlenmiş 2 holdout "
                "kriteri sağlanmış olmakla birlikte, bu durum bağımsız bir doğrulayıcı replikasyon olarak sınıflandırılamaz."
            ),
        }

        return explanations
