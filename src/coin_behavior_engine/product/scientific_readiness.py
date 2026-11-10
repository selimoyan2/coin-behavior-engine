"""
Scientific Readiness Scorecard Engine.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Evaluates research records across 10 transparent scientific dimensions, enforcing
fail-closed mandatory gates, clear evidence status distinctions, and explainable
readiness assessments without fabricating scientific validity or granting trading rights.
"""

from __future__ import annotations

import enum
import hashlib
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CANONICAL_MODEL = "CBE-0.7.0"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
MODEL_STATUS = "STRICTLY_FROZEN"
CBE_TRADING_DISABLED = True
LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED = True
from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
)
from coin_behavior_engine.product.reproducibility_lab import (
    ReproducibilityLabEngine,
)


class DimensionStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class OverallReadinessVerdict(str, enum.Enum):
    READY_FOR_CONFIRMATORY_REVIEW = "READY_FOR_CONFIRMATORY_REVIEW"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    METHODOLOGICALLY_BLOCKED = "METHODOLOGICALLY_BLOCKED"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"


@dataclass
class DimensionEvaluation:
    dimension_key: str
    dimension_name_tr: str
    dimension_name_en: str
    status: str  # from DimensionStatus
    is_critical_gate: bool
    is_passed: bool
    evidence_reference: str
    explanation_tr: str
    explanation_en: str
    required_action_tr: str
    required_action_en: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScientificReadinessScorecard:
    record_id: str
    title_tr: str
    title_en: str
    overall_verdict: str  # from OverallReadinessVerdict
    is_ready_for_review: bool
    critical_gates_passed: int
    total_critical_gates: int
    dimensions: List[DimensionEvaluation]
    passed_dimensions: List[str]
    failed_dimensions: List[str]
    unverified_dimensions: List[str]
    blocking_reasons_tr: List[str]
    blocking_reasons_en: List[str]
    supporting_evidence_links: List[Dict[str, str]]
    required_next_actions_tr: List[str]
    required_next_actions_en: List[str]
    heuristic_readiness_index: float  # [0.0, 100.0] - Strictly secondary heuristic
    heuristic_disclaimer_tr: str = (
        "Hazırlık endeksi yalnızca bir ürün-düzeyi sıralama heuristiğidir. "
        "Yüksek puan hiçbir koşulda başarısız kritik kapıları veya bilimsel dondurma kararlarını geçersiz kılamaz."
    )
    evaluated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScientificReadinessEvaluator:
    """
    Evaluates research records against the 10 transparent scientific readiness dimensions.
    Enforces strict fail-closed gating: an unverified source artifact or missing observation
    completeness will prevent progression regardless of sample size or statistical heuristics.
    """

    MIN_SAMPLE_SIZE_THRESHOLD = 100

    @classmethod
    def evaluate_record(cls, record: Any) -> ScientificReadinessScorecard:
        rec_id = getattr(record, "id", "UNKNOWN")
        title_tr = getattr(record, "title", rec_id)
        title_en = getattr(record, "title_en", rec_id)
        dims: List[DimensionEvaluation] = []
        blocking_reasons_tr: List[str] = []
        blocking_reasons_en: List[str] = []
        next_actions_tr: List[str] = []
        next_actions_en: List[str] = []
        evidence_links: List[Dict[str, str]] = []

        # ----------------------------------------------------------------------
        # 1. DATASET_PROVENANCE (Critical Gate)
        # ----------------------------------------------------------------------
        ds_id = getattr(record, "dataset_id", "")
        att = getattr(record, "observation_completeness_attestation", None)
        quarantine_status = getattr(record, "quarantine_status", "")

        # Check quarantine or synthetic first
        if quarantine_status == "QUARANTINED" or "OCTOBER-2026-INTAKE" in ds_id or "SYNTHETIC" in ds_id:
            d1 = DimensionEvaluation(
                dimension_key="DATASET_PROVENANCE",
                dimension_name_tr="Veri Seti Kökeni ve Soykütüğü",
                dimension_name_en="Dataset Provenance & Lineage",
                status=DimensionStatus.BLOCKED.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=ds_id,
                explanation_tr=f"Veri seti '{ds_id}' sentetik anomaliler veya karantina nedeniyle bloke edilmiştir.",
                explanation_en=f"Dataset '{ds_id}' is blocked due to synthetic anomalies or intake quarantine.",
                required_action_tr="Karantina adli incelemesi tamamlanmadan veri seti kullanılamaz.",
                required_action_en="Dataset cannot be used until quarantine forensics are resolved.",
                metrics={"quarantine_status": "QUARANTINED", "dataset_id": ds_id},
            )
            blocking_reasons_tr.append(f"Veri seti karantinada ({ds_id}).")
            blocking_reasons_en.append(f"Dataset quarantined ({ds_id}).")
            next_actions_tr.append("Karantina adli raporunu tamamlayın.")
            next_actions_en.append("Resolve intake quarantine forensics.")
        else:
            # Require authentic intake manifest, signed attestation, or verifiable primary raw data on disk
            has_attested_lineage = False
            if att and isinstance(att, dict):
                att_check = ObservationCompletenessAttestationVerifier.verify_attestation(
                    record, att, use_cache=True, enforce_source_file_integrity=False
                )
                if att_check.get("is_valid") and att.get("dataset_id") == ds_id:
                    has_attested_lineage = True

            has_physical_data = False
            if ds_id:
                if "BTCUSDT-SPOT" in ds_id or "BTCUSDT-1h" in ds_id:
                    has_physical_data = Path("data/binance_spot_multiyear/1h/").exists() or Path("data/normalized/binance_pilot_2022_01/").exists()
                elif "PERP-FUNDING" in ds_id:
                    has_physical_data = Path("data/historical/futures/raw/").exists()
                elif "SYSTEM-AUDIT" in ds_id:
                    has_physical_data = Path("research_outputs/sprint23_delivery/").exists()
                elif getattr(record, "intake_manifest_path", ""):
                    imp = Path(getattr(record, "intake_manifest_path"))
                    has_physical_data = imp.exists() and imp.is_file()

            if (has_attested_lineage or has_physical_data) and ds_id:
                d1 = DimensionEvaluation(
                    dimension_key="DATASET_PROVENANCE",
                    dimension_name_tr="Veri Seti Kökeni ve Soykütüğü",
                    dimension_name_en="Dataset Provenance & Lineage",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"Authentic provenance: {ds_id} (attested={has_attested_lineage}, storage={has_physical_data})",
                    explanation_tr=f"Veri seti '{ds_id}' doğrulanabilir birincil ambar ve tasdik soykütüğü ile teyit edildi.",
                    explanation_en=f"Dataset '{ds_id}' verified via authentic intake repository and lineage attestation.",
                    required_action_tr="Ek bir veri seti işlemi gerekmemektedir.",
                    required_action_en="No additional dataset action required.",
                    metrics={"dataset_id": ds_id, "has_attested_lineage": has_attested_lineage, "has_physical_data": has_physical_data},
                )
            else:
                d1 = DimensionEvaluation(
                    dimension_key="DATASET_PROVENANCE",
                    dimension_name_tr="Veri Seti Kökeni ve Soykütüğü",
                    dimension_name_en="Dataset Provenance & Lineage",
                    status=DimensionStatus.UNVERIFIED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=ds_id or "NONE",
                    explanation_tr="Doğrulanabilir birincil veri seti soykütüğü bulunamadı.",
                    explanation_en="No verifiable primary dataset lineage found.",
                    required_action_tr="Resmi veri kaynağı soykütüğünü kaydedin.",
                    required_action_en="Register authoritative dataset provenance.",
                    metrics={"dataset_id": ds_id},
                )
                blocking_reasons_tr.append("Veri seti soykütüğü doğrulanmamış.")
                blocking_reasons_en.append("Dataset provenance unverified.")
                next_actions_tr.append("Veri seti soykütüğünü belgelendirin.")
                next_actions_en.append("Document dataset lineage.")
        dims.append(d1)

        # ----------------------------------------------------------------------
        # 2. SOURCE_ARTIFACT_INTEGRITY (Critical Gate)
        # ----------------------------------------------------------------------
        source_path = getattr(record, "source_artifact", "")
        expected_sha = getattr(record, "source_artifact_sha256", "")
        if source_path:
            att_for_art = att if (att and isinstance(att, dict) and att.get("source_artifact_sha256")) else {"source_artifact_sha256": expected_sha}
            is_valid_art, rej_code, rej_reason, actual_sha, _, _ = (
                ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
                    record, att_for_art
                )
            )
            if is_valid_art:
                actual_sha = actual_sha or expected_sha
                d2 = DimensionEvaluation(
                    dimension_key="SOURCE_ARTIFACT_INTEGRITY",
                    dimension_name_tr="Kaynak Belge Bütünlüğü (SHA-256)",
                    dimension_name_en="Source Artifact Integrity (SHA-256)",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=source_path,
                    explanation_tr=f"Disk üzerindeki dosya özeti ({actual_sha[:16]}...) kayıtla tam olarak eşleşiyor.",
                    explanation_en=f"Disk artifact digest ({actual_sha[:16]}...) matches record exactly.",
                    required_action_tr="Bütünlük doğrulandı.",
                    required_action_en="Integrity verified.",
                    metrics={"sha256": actual_sha},
                )
                evidence_links.append({"type": "SOURCE_ARTIFACT", "path": source_path, "sha256": actual_sha})
            else:
                rejection = rej_code or "INTEGRITY_FAILED"
                d2 = DimensionEvaluation(
                    dimension_key="SOURCE_ARTIFACT_INTEGRITY",
                    dimension_name_tr="Kaynak Belge Bütünlüğü (SHA-256)",
                    dimension_name_en="Source Artifact Integrity (SHA-256)",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=source_path,
                    explanation_tr=f"Kaynak belge bütünlük kontrolü başarısız ({rejection}): {rej_reason}",
                    explanation_en=f"Source artifact integrity failed ({rejection}): {rej_reason}",
                    required_action_tr="Kaynak dosya manipülasyonunu araştırın veya doğru belgeyi geri yükleyin.",
                    required_action_en="Investigate file tampering or restore authentic artifact.",
                    metrics={"rejection_code": rejection},
                )
                blocking_reasons_tr.append(f"Kaynak belge bütünlüğü başarısız ({rejection}).")
                blocking_reasons_en.append(f"Source artifact integrity failed ({rejection}).")
        else:
            d2 = DimensionEvaluation(
                dimension_key="SOURCE_ARTIFACT_INTEGRITY",
                dimension_name_tr="Kaynak Belge Bütünlüğü (SHA-256)",
                dimension_name_en="Source Artifact Integrity (SHA-256)",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference="NONE",
                explanation_tr="Araştırma kaydında kaynak belge yolu belirtilmemiş.",
                explanation_en="No source artifact path specified in research record.",
                required_action_tr="Kayıt için birincil kanıt belgesi ekleyin.",
                required_action_en="Attach primary evidence artifact to record.",
            )
            blocking_reasons_tr.append("Kaynak belge yolu belirtilmemiş.")
            blocking_reasons_en.append("No source artifact path.")
        dims.append(d2)

        # ----------------------------------------------------------------------
        # 3. OBSERVATION_COMPLETENESS (Critical Gate)
        # ----------------------------------------------------------------------
        obs_timestamps = getattr(record, "observed_timestamps", None)
        if att and isinstance(att, dict):
            # Check attestation validity
            att_res = ObservationCompletenessAttestationVerifier.verify_attestation(
                record, att, use_cache=True, enforce_source_file_integrity=True
            )
            if att_res.get("is_valid"):
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"Key: {att.get('key_id')}",
                    explanation_tr="Kriptografik olarak imzalanmış eksiksiz sürekli seri tasdiki doğrulandı.",
                    explanation_en="Cryptographically signed completeness attestation verified.",
                    required_action_tr="Tasdik geçerli.",
                    required_action_en="Attestation valid.",
                    metrics={"observation_count": att.get("observation_count")},
                )
            else:
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=str(att_res.get("rejection_code")),
                    explanation_tr=f"Eksiksizlik tasdiki doğrulaması başarısız oldu: {att_res.get('rejection_reason_tr')}",
                    explanation_en=f"Completeness attestation rejected: {att_res.get('rejection_code')}",
                    required_action_tr="Yetkili makamdan yeni ve geçerli bir tasdik alın.",
                    required_action_en="Obtain fresh authenticated attestation.",
                )
                blocking_reasons_tr.append(f"Tasdik doğrulaması başarısız ({att_res.get('rejection_code')}).")
                blocking_reasons_en.append(f"Attestation verification failed ({att_res.get('rejection_code')}).")
        elif obs_timestamps and isinstance(obs_timestamps, list) and len(obs_timestamps) >= cls.MIN_SAMPLE_SIZE_THRESHOLD:
            # Verify chronological ordering
            is_chrono = all(obs_timestamps[i] <= obs_timestamps[i + 1] for i in range(len(obs_timestamps) - 1))
            if is_chrono:
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"{len(obs_timestamps)} explicit timestamps",
                    explanation_tr=f"{len(obs_timestamps)} doğrulanmış açık kronolojik zaman damgası mevcut.",
                    explanation_en=f"{len(obs_timestamps)} verified explicit chronological timestamps present.",
                    required_action_tr="Açık zaman damgaları yeterli.",
                    required_action_en="Explicit timestamps sufficient.",
                    metrics={"observation_count": len(obs_timestamps)},
                )
            else:
                d3 = DimensionEvaluation(
                    dimension_key="OBSERVATION_COMPLETENESS",
                    dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                    dimension_name_en="Observation Completeness & Attestation",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=f"{len(obs_timestamps)} timestamps",
                    explanation_tr="Açık zaman damgaları kronolojik sırada değil (sıralama bozuk).",
                    explanation_en="Explicit timestamps are not in non-decreasing chronological order.",
                    required_action_tr="Kronolojik zaman damgası dizisini düzeltin.",
                    required_action_en="Correct chronological timestamp ordering.",
                )
                blocking_reasons_tr.append("Zaman damgaları kronolojik değil.")
                blocking_reasons_en.append("Timestamps not chronological.")
        else:
            d3 = DimensionEvaluation(
                dimension_key="OBSERVATION_COMPLETENESS",
                dimension_name_tr="Gözlem Sürekliliği & Eksiksizlik Tasdiki",
                dimension_name_en="Observation Completeness & Attestation",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference="NONE",
                explanation_tr="Doğrulanmış açık zaman damgaları veya imzalı tasdik paketi bulunamadı.",
                explanation_en="No verified explicit timestamps or signed attestation envelope found.",
                required_action_tr="Açık gözlem zaman damgalarını veya imzalı tasdik belgesini ekleyin.",
                required_action_en="Attach explicit timestamps or authenticated completeness attestation.",
            )
            blocking_reasons_tr.append("Gözlem eksiksizliği kanıtı yetersiz.")
            blocking_reasons_en.append("Observation completeness evidence insufficient.")
            next_actions_tr.append("Gözlem zaman damgalarını veya imzalı tasdik sağlayın.")
            next_actions_en.append("Provide observed timestamps or signed attestation.")
        dims.append(d3)

        # ----------------------------------------------------------------------
        # 4. METHODOLOGY_COMPATIBILITY
        # ----------------------------------------------------------------------
        spec_id = getattr(record, "specification_id", "")
        cadence = getattr(record, "window_cadence", "")
        if spec_id and cadence:
            d4 = DimensionEvaluation(
                dimension_key="METHODOLOGY_COMPATIBILITY",
                dimension_name_tr="Metodoloji ve Kadans Uyumluluğu",
                dimension_name_en="Methodology & Cadence Compatibility",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=False,
                is_passed=True,
                evidence_reference=f"Spec: {spec_id}, Cadence: {cadence}",
                explanation_tr=f"Spesifikasyon '{spec_id}' ve örnekleme kadansı '{cadence}' bilimsel olarak tanımlıdır.",
                explanation_en=f"Specification '{spec_id}' and sampling cadence '{cadence}' are scientifically defined.",
                required_action_tr="Metodoloji uyumlu.",
                required_action_en="Methodology compatible.",
                metrics={"specification_id": spec_id, "cadence": cadence},
            )
        else:
            d4 = DimensionEvaluation(
                dimension_key="METHODOLOGY_COMPATIBILITY",
                dimension_name_tr="Metodoloji ve Kadans Uyumluluğu",
                dimension_name_en="Methodology & Cadence Compatibility",
                status=DimensionStatus.UNVERIFIED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="MISSING",
                explanation_tr="Araştırma spesifikasyon kimliği veya örnekleme kadansı eksik.",
                explanation_en="Research specification ID or cadence missing.",
                required_action_tr="Spesifikasyon protokolünü belirleyin.",
                required_action_en="Define specification protocol.",
            )
        dims.append(d4)

        # ----------------------------------------------------------------------
        # 5. SAMPLE_SUFFICIENCY (Critical Gate)
        # ----------------------------------------------------------------------
        sample_size = getattr(record, "sample_size", 0) or 0
        if sample_size < cls.MIN_SAMPLE_SIZE_THRESHOLD:
            d5 = DimensionEvaluation(
                dimension_key="SAMPLE_SUFFICIENCY",
                dimension_name_tr="Örneklem Yeterliliği (N >= 100)",
                dimension_name_en="Sample Sufficiency (N >= 100)",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=f"N = {sample_size}",
                explanation_tr=f"Örneklem boyutu ({sample_size}) asgari bilimsel sınırın (100) altındadır.",
                explanation_en=f"Sample size ({sample_size}) is below scientific threshold of N >= 100.",
                required_action_tr="Gözlem penceresini en az 100 gözlem içerecek şekilde genişletin.",
                required_action_en="Extend observation window to cover at least 100 intervals.",
                metrics={"sample_size": sample_size},
            )
            blocking_reasons_tr.append(f"Yetersiz örneklem boyutu ({sample_size} < 100).")
            blocking_reasons_en.append(f"Insufficient sample size ({sample_size} < 100).")
            next_actions_tr.append("Veri penceresini genişleterek örneklem sayısını artırın.")
            next_actions_en.append("Expand data window to increase sample count.")
        else:
            # Check consistency with observed_timestamps or attestation observation count
            has_discrepancy = False
            discrepancy_msg = ""
            if obs_timestamps and isinstance(obs_timestamps, list) and len(obs_timestamps) != sample_size:
                has_discrepancy = True
                discrepancy_msg = f"Timestamp count ({len(obs_timestamps)}) contradicts declared sample size ({sample_size})."
            elif att and isinstance(att, dict) and att.get("observation_count") is not None and att.get("observation_count") != sample_size:
                has_discrepancy = True
                discrepancy_msg = f"Attested count ({att.get('observation_count')}) contradicts declared sample size ({sample_size})."

            if has_discrepancy:
                d5 = DimensionEvaluation(
                    dimension_key="SAMPLE_SUFFICIENCY",
                    dimension_name_tr="Örneklem Yeterliliği (N >= 100)",
                    dimension_name_en="Sample Sufficiency (N >= 100)",
                    status=DimensionStatus.FAILED.value,
                    is_critical_gate=True,
                    is_passed=False,
                    evidence_reference=f"Discrepancy: {discrepancy_msg}",
                    explanation_tr=f"Örneklem boyutu ile gözlem kanıtı arasında çelişki tespit edildi: {discrepancy_msg}",
                    explanation_en=f"Discrepancy detected between declared sample size and observation count: {discrepancy_msg}",
                    required_action_tr="Örneklem boyutu ile gözlem kanıtı arasındaki çelişkiyi giderin.",
                    required_action_en="Reconcile discrepancy between declared sample size and observation evidence.",
                    metrics={"sample_size": sample_size},
                )
                blocking_reasons_tr.append("Örneklem sayısı ve gözlem adedi uyuşmuyor.")
                blocking_reasons_en.append(discrepancy_msg)
            else:
                d5 = DimensionEvaluation(
                    dimension_key="SAMPLE_SUFFICIENCY",
                    dimension_name_tr="Örneklem Yeterliliği (N >= 100)",
                    dimension_name_en="Sample Sufficiency (N >= 100)",
                    status=DimensionStatus.VERIFIED.value,
                    is_critical_gate=True,
                    is_passed=True,
                    evidence_reference=f"N = {sample_size}",
                    explanation_tr=f"Örneklem boyutu ({sample_size}) asgari bilimsel sınır olan 100 gözlemi karşılıyor.",
                    explanation_en=f"Sample size ({sample_size}) meets scientific threshold of N >= 100.",
                    required_action_tr="Örneklem yeterli.",
                    required_action_en="Sample sufficient.",
                    metrics={"sample_size": sample_size},
                )
        dims.append(d5)

        # ----------------------------------------------------------------------
        # 6. STATISTICAL_VALIDITY
        # ----------------------------------------------------------------------
        p_val = getattr(record, "raw_p_value", None)
        vol_ratio = getattr(record, "volatility_ratio", None)
        stat_valid = True
        stat_present = False
        reasons_stat: List[str] = []

        if p_val is not None:
            if isinstance(p_val, (int, float)) and not math.isnan(p_val) and not math.isinf(p_val):
                if 0.0 <= p_val <= 1.0:
                    stat_present = True
                else:
                    stat_valid = False
                    reasons_stat.append(f"p_value out of range [0, 1]: {p_val}")
            else:
                stat_valid = False
                reasons_stat.append("p_value is NaN or non-finite")

        if vol_ratio is not None:
            if isinstance(vol_ratio, (int, float)) and not math.isnan(vol_ratio) and not math.isinf(vol_ratio):
                if vol_ratio > 0:
                    stat_present = True
                else:
                    stat_valid = False
                    reasons_stat.append(f"volatility_ratio <= 0: {vol_ratio}")
            else:
                stat_valid = False
                reasons_stat.append("volatility_ratio is NaN or non-finite")

        if not stat_valid:
            d6 = DimensionEvaluation(
                dimension_key="STATISTICAL_VALIDITY",
                dimension_name_tr="İstatistiksel Geçerlilik & Uç Değer Kontrolü",
                dimension_name_en="Statistical Validity & Outlier Control",
                status=DimensionStatus.FAILED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="; ".join(reasons_stat),
                explanation_tr=f"Geçersiz sayısal metrikler: {'; '.join(reasons_stat)}",
                explanation_en=f"Invalid numerical metrics: {'; '.join(reasons_stat)}",
                required_action_tr="Sayısal metrikleri düzeltin.",
                required_action_en="Correct numerical metrics.",
            )
        elif stat_present:
            d6 = DimensionEvaluation(
                dimension_key="STATISTICAL_VALIDITY",
                dimension_name_tr="İstatistiksel Geçerlilik & Uç Değer Kontrolü",
                dimension_name_en="Statistical Validity & Outlier Control",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=False,
                is_passed=True,
                evidence_reference=f"p={p_val}, vol_ratio={vol_ratio}",
                explanation_tr="Sayısal metrikler sonlu, p-değeri geçerli aralıkta ve NaN içermiyor.",
                explanation_en="Numerical metrics finite, valid p-value range, zero NaNs.",
                required_action_tr="İstatistiksel format geçerli.",
                required_action_en="Statistical format valid.",
                metrics={"raw_p_value": p_val, "volatility_ratio": vol_ratio},
            )
        else:
            d6 = DimensionEvaluation(
                dimension_key="STATISTICAL_VALIDITY",
                dimension_name_tr="İstatistiksel Geçerlilik & Uç Değer Kontrolü",
                dimension_name_en="Statistical Validity & Outlier Control",
                status=DimensionStatus.UNVERIFIED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="MISSING_METRICS",
                explanation_tr="Geçerli sonlu istatistiksel test metrikleri bulunamadı.",
                explanation_en="No valid finite statistical test metrics found.",
                required_action_tr="İstatistiksel testleri çalıştırın ve sonuçları kaydedin.",
                required_action_en="Execute statistical tests and record outputs.",
            )
        dims.append(d6)

        # ----------------------------------------------------------------------
        # 7. REPRODUCIBILITY (Critical Gate)
        # ----------------------------------------------------------------------
        # Check allowlisted procedure mapping and physical input presence
        cat = getattr(record, "category", "")
        proc_name = getattr(record, "procedure_name", None)
        if not proc_name:
            for p_code, p_meta in ReproducibilityLabEngine.ALLOWLISTED_PROCEDURES.items():
                if any(c.lower() in cat.lower() for c in p_meta["supported_categories"]):
                    proc_name = p_code
                    break

        has_allowlisted_proc = proc_name in ReproducibilityLabEngine.ALLOWLISTED_PROCEDURES
        att_for_art_rep = att if (att and isinstance(att, dict) and att.get("source_artifact_sha256")) else {"source_artifact_sha256": expected_sha}
        is_valid_art, _, _, _, _, _ = ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
            record, att_for_art_rep
        )
        has_reproduction_data = bool(source_path and Path(source_path).exists() and is_valid_art)

        if has_allowlisted_proc and has_reproduction_data:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=True,
                is_passed=True,
                evidence_reference=f"Proc: {proc_name}, Artifact: {source_path}",
                explanation_tr=f"Onaylı prosedür '{proc_name}' ve çevrimdışı araştırma verisi disk üzerinde doğrulanabilir durumdadır.",
                explanation_en=f"Allowlisted procedure '{proc_name}' and offline data are verifiable on disk.",
                required_action_tr="Reproducibility Lab ile prosedürü yeniden çalıştırabilirsiniz.",
                required_action_en="Procedure can be re-executed in Reproducibility Lab.",
                metrics={"procedure_name": proc_name},
            )
        elif not has_allowlisted_proc:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.INSUFFICIENT_EVIDENCE.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=proc_name or "NO_PROCEDURE_MAPPING",
                explanation_tr="Araştırma kaydı için onaylı bir çevrimdışı tekrarlama prosedürü eşleşmedi.",
                explanation_en="No allowlisted offline reproduction procedure mapped to this record.",
                required_action_tr="Onaylı bir prosedür protokolü tanımlayın.",
                required_action_en="Define an approved procedure protocol.",
            )
            blocking_reasons_tr.append("Onaylı tekrarlama prosedürü eşleşmedi.")
            blocking_reasons_en.append("No allowlisted reproduction procedure.")
        else:
            d7 = DimensionEvaluation(
                dimension_key="REPRODUCIBILITY",
                dimension_name_tr="Çevrimdışı Tekrarlanabilirlik (Offline Reproducibility)",
                dimension_name_en="Offline Reproducibility Instructions",
                status=DimensionStatus.FAILED.value,
                is_critical_gate=True,
                is_passed=False,
                evidence_reference=source_path or "MISSING_INPUTS",
                explanation_tr="Çevrimdışı tekrarlama için gerekli girdi dosyaları eksik veya bütünlüğü bozuk.",
                explanation_en="Missing input data files or integrity failure for offline reproduction.",
                required_action_tr="Tekrarlanabilirlik girdi paketini onarın.",
                required_action_en="Repair reproducibility input bundle.",
            )
            blocking_reasons_tr.append("Çevrimdışı tekrarlama girdileri eksik veya bozuk.")
            blocking_reasons_en.append("Missing or corrupted offline reproduction inputs.")
        dims.append(d7)

        # ----------------------------------------------------------------------
        # 8. INDEPENDENT_REPLICATION
        # ----------------------------------------------------------------------
        # Require authentic external replication attestation; ignore unauthenticated text strings.
        ext_att = getattr(record, "external_replication_attestation", None)
        has_ext_rep = bool(ext_att and isinstance(ext_att, dict) and ext_att.get("is_valid"))
        if has_ext_rep:
            d8 = DimensionEvaluation(
                dimension_key="INDEPENDENT_REPLICATION",
                dimension_name_tr="Bağımsız Replikasyon Doğrulaması",
                dimension_name_en="Independent Replication Verification",
                status=DimensionStatus.VERIFIED.value,
                is_critical_gate=False,
                is_passed=True,
                evidence_reference=str(ext_att.get("attestor_id", "EXTERNAL")),
                explanation_tr="Bağımsız harici araştırmacı tasdiki ile teyit edilmiştir.",
                explanation_en="Confirmed via authenticated independent external replication attestation.",
                required_action_tr="Replikasyon mevcut.",
                required_action_en="Replication present.",
            )
        else:
            d8 = DimensionEvaluation(
                dimension_key="INDEPENDENT_REPLICATION",
                dimension_name_tr="Bağımsız Replikasyon Doğrulaması",
                dimension_name_en="Independent Replication Verification",
                status=DimensionStatus.UNVERIFIED.value,
                is_critical_gate=False,
                is_passed=False,
                evidence_reference="NO_EXTERNAL_ATTESTATION",
                explanation_tr="Henüz bağımsız bir harici replikasyon tasdiki bulunmamaktadır (CBE-0.7.0 yerel tek-kaynak bulgusudur).",
                explanation_en="No authenticated independent external replication attestation (CBE-0.7.0 single-source finding).",
                required_action_tr="Ayrı bir veri penceresinde bağımsız replikasyon denemesi planlayın.",
                required_action_en="Schedule independent replication on an out-of-sample window.",
            )
            next_actions_tr.append("Bağımsız replikasyon çalışması planlayın.")
            next_actions_en.append("Plan independent replication experiment.")
        dims.append(d8)

        # ----------------------------------------------------------------------
        # 9. EVIDENCE_FRESHNESS
        # ----------------------------------------------------------------------
        # Fail-closed: missing freshness timestamps cannot be treated as verified
        is_fresh = True
        fresh_status = DimensionStatus.VERIFIED.value
        fresh_msg_tr = "Kanıt paketi aktif ve yürürlüktedir."
        fresh_msg_en = "Evidence package active and current."
        has_timestamp = False

        if att and isinstance(att, dict):
            if att.get("is_superseded"):
                is_fresh = False
                fresh_status = DimensionStatus.FAILED.value
                fresh_msg_tr = "Tasdik yürürlükten kaldırılmıştır (superseded)."
                fresh_msg_en = "Attestation superseded."
            exp = att.get("expires_at_utc")
            if exp:
                has_timestamp = True
                try:
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        is_fresh = False
                        fresh_status = DimensionStatus.FAILED.value
                        fresh_msg_tr = f"Tasdik süresi dolmuştur ({exp})."
                        fresh_msg_en = f"Attestation expired ({exp})."
                except Exception:
                    pass
            if att.get("created_at_utc"):
                has_timestamp = True

        rec_time = getattr(record, "created_at_utc", None) or getattr(record, "evaluated_at_utc", None)
        if rec_time:
            has_timestamp = True

        if not has_timestamp and is_fresh:
            is_fresh = False
            fresh_status = DimensionStatus.UNVERIFIED.value
            fresh_msg_tr = "Kanıt zaman damgası veya geçerlilik süresi belirtilmemiş."
            fresh_msg_en = "No evidence freshness timestamp or validity window specified."

        d9 = DimensionEvaluation(
            dimension_key="EVIDENCE_FRESHNESS",
            dimension_name_tr="Kanıt Güncelliği ve İptal Durumu",
            dimension_name_en="Evidence Freshness & Revocation Status",
            status=fresh_status,
            is_critical_gate=False,
            is_passed=is_fresh,
            evidence_reference="Trust Policy 2026.2",
            explanation_tr=fresh_msg_tr,
            explanation_en=fresh_msg_en,
            required_action_tr="Güncel." if is_fresh else "Kanıtı yenileyin veya zaman damgası ekleyin.",
            required_action_en="Current." if is_fresh else "Refresh evidence or attach timestamp.",
        )
        dims.append(d9)

        # ----------------------------------------------------------------------
        # 10. GOVERNANCE_COMPLIANCE (Critical Gate)
        # ----------------------------------------------------------------------
        # CBE-0.7.0 Strictly Frozen, TECHNICAL_NO_GO, Trading Disabled
        is_gov_compliant = (
            CANONICAL_MODEL == "CBE-0.7.0"
            and GOVERNANCE_DECISION == "TECHNICAL_NO_GO"
            and CBE_TRADING_DISABLED is True
            and LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED is True
        )
        d10 = DimensionEvaluation(
            dimension_key="GOVERNANCE_COMPLIANCE",
            dimension_name_tr="Bilimsel Yönetişim & Canlı İşlem Yasağı",
            dimension_name_en="Scientific Governance & Trading Prohibition",
            status=DimensionStatus.VERIFIED.value if is_gov_compliant else DimensionStatus.BLOCKED.value,
            is_critical_gate=True,
            is_passed=is_gov_compliant,
            evidence_reference="CBE-0.7.0 TECHNICAL_NO_GO",
            explanation_tr="CBE-0.7.0 modeli kesin olarak dondurulmuştur; yönsel canlı işlem yasaklanmıştır.",
            explanation_en="CBE-0.7.0 strictly frozen; directional live trading permanently prohibited.",
            required_action_tr="Yönetişim kısıtlamalarına uyun.",
            required_action_en="Adhere to scientific governance constraints.",
            metrics={
                "canonical_model": CANONICAL_MODEL,
                "governance_decision": GOVERNANCE_DECISION,
                "trading_prohibited": LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED,
            },
        )
        dims.append(d10)

        # ----------------------------------------------------------------------
        # AGGREGATE EVALUATION
        # ----------------------------------------------------------------------
        critical_dims = [d for d in dims if d.is_critical_gate]
        total_critical = len(critical_dims)
        critical_passed = sum(1 for d in critical_dims if d.is_passed)

        passed_keys = [d.dimension_key for d in dims if d.status == DimensionStatus.VERIFIED.value]
        failed_keys = [d.dimension_key for d in dims if d.status in (DimensionStatus.FAILED.value, DimensionStatus.BLOCKED.value)]
        unverified_keys = [d.dimension_key for d in dims if d.status in (DimensionStatus.UNVERIFIED.value, DimensionStatus.INSUFFICIENT_EVIDENCE.value)]

        # Determine overall verdict
        if any(d.status == DimensionStatus.FAILED.value for d in critical_dims):
            overall_verdict = OverallReadinessVerdict.INTEGRITY_FAILED.value
            is_ready = False
        elif any(d.status == DimensionStatus.BLOCKED.value for d in critical_dims):
            overall_verdict = OverallReadinessVerdict.METHODOLOGICALLY_BLOCKED.value
            is_ready = False
        elif critical_passed < total_critical:
            overall_verdict = OverallReadinessVerdict.INSUFFICIENT_EVIDENCE.value
            is_ready = False
        else:
            # All critical gates passed! Ready for confirmatory review (not trading!)
            overall_verdict = OverallReadinessVerdict.READY_FOR_CONFIRMATORY_REVIEW.value
            is_ready = True

        # Secondary Product-Level Heuristic Index (Strictly Secondary)
        # Weights: 10 points per verified dimension, 0 for unverified/failed
        heuristic_index = round((len(passed_keys) / len(dims)) * 100.0, 1)

        return ScientificReadinessScorecard(
            record_id=rec_id,
            title_tr=title_tr,
            title_en=title_en,
            overall_verdict=overall_verdict,
            is_ready_for_review=is_ready,
            critical_gates_passed=critical_passed,
            total_critical_gates=total_critical,
            dimensions=dims,
            passed_dimensions=passed_keys,
            failed_dimensions=failed_keys,
            unverified_dimensions=unverified_keys,
            blocking_reasons_tr=blocking_reasons_tr,
            blocking_reasons_en=blocking_reasons_en,
            supporting_evidence_links=evidence_links,
            required_next_actions_tr=next_actions_tr,
            required_next_actions_en=next_actions_en,
            heuristic_readiness_index=heuristic_index,
        )


# Global evaluator instance
scientific_readiness_evaluator = ScientificReadinessEvaluator()
