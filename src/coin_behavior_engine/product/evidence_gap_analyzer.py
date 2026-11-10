"""
Evidence Gap Analyzer.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Systematically detects missing, contradictory, outdated, or insufficient evidence
across 14 scientific gap categories, producing actionable research remediation steps.
"""

from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

CANONICAL_MODEL = "CBE-0.7.0"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
MODEL_STATUS = "STRICTLY_FROZEN"
CBE_TRADING_DISABLED = True
from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
)


class GapCategory(str, enum.Enum):
    MISSING_SOURCE_ARTIFACT = "MISSING_SOURCE_ARTIFACT"
    INVALID_ARTIFACT_SIGNATURE = "INVALID_ARTIFACT_SIGNATURE"
    MISSING_DATASET_PROVENANCE = "MISSING_DATASET_PROVENANCE"
    INCOMPLETE_OBSERVATION_HISTORY = "INCOMPLETE_OBSERVATION_HISTORY"
    INSUFFICIENT_SAMPLE_SIZE = "INSUFFICIENT_SAMPLE_SIZE"
    INSUFFICIENT_SHARED_OBSERVATIONS = "INSUFFICIENT_SHARED_OBSERVATIONS"
    METHODOLOGY_MISMATCH = "METHODOLOGY_MISMATCH"
    MISSING_INDEPENDENT_REPLICATION = "MISSING_INDEPENDENT_REPLICATION"
    CONFLICTING_RESEARCH_FINDINGS = "CONFLICTING_RESEARCH_FINDINGS"
    UNSUPPORTED_STATISTICAL_CLAIM = "UNSUPPORTED_STATISTICAL_CLAIM"
    SUPERSEDED_EVIDENCE = "SUPERSEDED_EVIDENCE"
    EXPIRED_ATTESTATION = "EXPIRED_ATTESTATION"
    MISSING_REPRODUCIBILITY_INSTRUCTIONS = "MISSING_REPRODUCIBILITY_INSTRUCTIONS"
    MISSING_GOVERNANCE_APPROVAL = "MISSING_GOVERNANCE_APPROVAL"


class GapSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class EvidenceGap:
    gap_id: str
    record_id: str
    gap_category: str  # from GapCategory
    severity: str      # from GapSeverity
    is_blocking: bool
    title_tr: str
    title_en: str
    explanation_tr: str
    explanation_en: str
    supporting_evidence: str
    suggested_research_action_tr: str
    suggested_research_action_en: str
    resolution_criteria_tr: str
    resolution_criteria_en: str
    detected_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceGapAnalyzer:
    """
    Automated scientific gap detector. Analyzes individual research records
    and entire catalogs to produce transparent, traceable research tasks.
    """

    MIN_SAMPLE_THRESHOLD = 100

    @classmethod
    def analyze_record(cls, record: Any) -> List[EvidenceGap]:
        gaps: List[EvidenceGap] = []
        rec_id = getattr(record, "id", "UNKNOWN")

        # 1. MISSING_SOURCE_ARTIFACT
        src_path = getattr(record, "source_artifact", "")
        if not src_path or not Path(src_path).exists():
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-01",
                    record_id=rec_id,
                    gap_category=GapCategory.MISSING_SOURCE_ARTIFACT.value,
                    severity=GapSeverity.CRITICAL.value,
                    is_blocking=True,
                    title_tr="Fiziksel Kaynak Araştırma Dosyası Bulunamadı",
                    title_en="Physical Source Research Artifact Missing",
                    explanation_tr=f"Belirtilen kaynak araştırma dosyası '{src_path}' disk üzerinde bulunamadı.",
                    explanation_en=f"Specified source artifact path '{src_path}' does not exist on disk.",
                    supporting_evidence=f"Path checked: {src_path}",
                    suggested_research_action_tr="Kaynak araştırma dosyasını birincil veri ambarından veya arşivden geri yükleyin.",
                    suggested_research_action_en="Restore source research artifact from primary repository or archive.",
                    resolution_criteria_tr="Kaynak dosyanın diskte doğrulanabilir şekilde bulunması ve SHA-256 mutabakatı.",
                    resolution_criteria_en="Source artifact present on disk with matching SHA-256 digest.",
                )
            )

        # 2. INVALID_ARTIFACT_SIGNATURE
        expected_sha = getattr(record, "source_artifact_sha256", "")
        if src_path and Path(src_path).exists():
            actual_sha = hashlib.sha256(Path(src_path).read_bytes()).hexdigest()
            if actual_sha != expected_sha:
                gaps.append(
                    EvidenceGap(
                        gap_id=f"GAP-{rec_id}-02",
                        record_id=rec_id,
                        gap_category=GapCategory.INVALID_ARTIFACT_SIGNATURE.value,
                        severity=GapSeverity.CRITICAL.value,
                        is_blocking=True,
                        title_tr="Kaynak Belge SHA-256 Bütünlük Uyuşmazlığı",
                        title_en="Source Artifact SHA-256 Integrity Mismatch",
                        explanation_tr=f"Disk üzerindeki dosya özeti ({actual_sha[:16]}...) kayıtla uyuşmuyor.",
                        explanation_en=f"Disk file digest ({actual_sha[:16]}...) contradicts expected record digest.",
                        supporting_evidence=f"Actual: {actual_sha}, Expected: {expected_sha}",
                        suggested_research_action_tr="Dosya manipülasyonunu inceleyin veya güvenilir kopyayı temin edin.",
                        suggested_research_action_en="Investigate file tampering or restore authentic copy.",
                        resolution_criteria_tr="Fiziksel dosya özetinin kayıtlı özetle tam mutabakatı.",
                        resolution_criteria_en="Exact match between physical file digest and record metadata.",
                    )
                )

        # 3. MISSING_DATASET_PROVENANCE
        ds_id = getattr(record, "dataset_id", "")
        if not ds_id or getattr(record, "quarantine_status", "") == "QUARANTINED":
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-03",
                    record_id=rec_id,
                    gap_category=GapCategory.MISSING_DATASET_PROVENANCE.value,
                    severity=GapSeverity.CRITICAL.value,
                    is_blocking=True,
                    title_tr="Veri Seti Kökeni Eksik veya Karantinaya Alınmış",
                    title_en="Dataset Provenance Missing or Quarantined",
                    explanation_tr=f"Veri seti '{ds_id}' doğrulanabilir birincil kaynağa bağlı değil ya da karantinada.",
                    explanation_en=f"Dataset '{ds_id}' has unverified origin or is under quarantine.",
                    supporting_evidence=f"Dataset: {ds_id}, Quarantine: {getattr(record, 'quarantine_status', 'NONE')}",
                    suggested_research_action_tr="Veri seti için tam borsa API intakelog ve SHA-256 soykütüğü kaydedin.",
                    suggested_research_action_en="Record complete exchange API intake log and SHA-256 lineage.",
                    resolution_criteria_tr="Karantinanın kaldırılması ve veri soykütüğünün doğrulanması.",
                    resolution_criteria_en="Quarantine resolution and provenance verification.",
                )
            )

        # 4. INCOMPLETE_OBSERVATION_HISTORY
        att = getattr(record, "observation_completeness_attestation", None)
        obs_timestamps = getattr(record, "observed_timestamps", None)
        has_attestation = False
        if att and isinstance(att, dict):
            att_check = ObservationCompletenessAttestationVerifier.verify_attestation(
                record, att, use_cache=True, enforce_source_file_integrity=False
            )
            has_attestation = bool(att_check.get("is_valid"))

        has_explicit = bool(obs_timestamps and len(obs_timestamps) >= cls.MIN_SAMPLE_THRESHOLD)

        if not has_attestation and not has_explicit:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-04",
                    record_id=rec_id,
                    gap_category=GapCategory.INCOMPLETE_OBSERVATION_HISTORY.value,
                    severity=GapSeverity.HIGH.value,
                    is_blocking=True,
                    title_tr="Gözlem Geçmişi Eksik veya Doğrulanmamış",
                    title_en="Observation History Incomplete or Unattested",
                    explanation_tr="Serinin sürekli ve eksiksiz olduğunu kanıtlayan açık zaman damgaları veya imzalı tasdik yok.",
                    explanation_en="No verified explicit timestamps or cryptographic attestation proving completeness.",
                    supporting_evidence="Both explicit timestamp list and valid signed attestation are absent.",
                    suggested_research_action_tr="Yetkili veri otoritesinden RFC-8785 tasdik paketi temin edin.",
                    suggested_research_action_en="Obtain an RFC-8785 signed attestation package from authority.",
                    resolution_criteria_tr="Geçerli bir HMAC-SHA256 tasdikinin veya açık damgaların eklenmesi.",
                    resolution_criteria_en="Valid HMAC-SHA256 attestation or complete timestamp grid attached.",
                )
            )

        # 5. INSUFFICIENT_SAMPLE_SIZE
        sample_size = getattr(record, "sample_size", 0) or 0
        if sample_size < cls.MIN_SAMPLE_THRESHOLD:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-05",
                    record_id=rec_id,
                    gap_category=GapCategory.INSUFFICIENT_SAMPLE_SIZE.value,
                    severity=GapSeverity.HIGH.value,
                    is_blocking=True,
                    title_tr=f"Yetersiz Örneklem Boyutu (N={sample_size} < 100)",
                    title_en=f"Insufficient Sample Size (N={sample_size} < 100)",
                    explanation_tr=f"Mevcut örneklem boyutu ({sample_size}) asgari bilimsel sınırın (100) altındadır.",
                    explanation_en=f"Sample size ({sample_size}) does not meet the minimum statistical floor of 100.",
                    supporting_evidence=f"Sample size: {sample_size}",
                    suggested_research_action_tr="Gözlem aralığını en az 100 bar/olay içerecek şekilde genişletin.",
                    suggested_research_action_en="Broaden observation window to cover at least 100 intervals.",
                    resolution_criteria_tr="Örneklem sayısının N >= 100 seviyesine ulaşması.",
                    resolution_criteria_en="Sample size reaching N >= 100.",
                )
            )

        # 6. INSUFFICIENT_SHARED_OBSERVATIONS (Evaluated in comparison context, flagged here if interval count low)
        obs_intervals = getattr(record, "observation_interval_count", 0) or 0
        if obs_intervals > 0 and obs_intervals < cls.MIN_SAMPLE_THRESHOLD:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-06",
                    record_id=rec_id,
                    gap_category=GapCategory.INSUFFICIENT_SHARED_OBSERVATIONS.value,
                    severity=GapSeverity.MEDIUM.value,
                    is_blocking=False,
                    title_tr="Gözlem Penceresi Potansiyel Olarak Yetersiz",
                    title_en="Observation Window Potentially Insufficient for Cross-Comparison",
                    explanation_tr=f"Gözlem penceresi aralık sayısı ({obs_intervals}) ortak kesişim için dar kalabilir.",
                    explanation_en=f"Observation interval count ({obs_intervals}) may fail shared overlap floor.",
                    supporting_evidence=f"Interval count: {obs_intervals}",
                    suggested_research_action_tr="Karşılaştırma için daha geniş geçmişe sahip adaylar seçin.",
                    suggested_research_action_en="Pair with candidates having wider overlapping spans.",
                    resolution_criteria_tr="İki kayıt arasında ortak N >= 100 doğrulanmış kesişim sağlanması.",
                    resolution_criteria_en="Verified shared intersection of N >= 100 between records.",
                )
            )

        # 7. METHODOLOGY_MISMATCH
        cat = getattr(record, "category", "")
        cadence = getattr(record, "window_cadence", "")
        if not cat or not cadence:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-07",
                    record_id=rec_id,
                    gap_category=GapCategory.METHODOLOGY_MISMATCH.value,
                    severity=GapSeverity.HIGH.value,
                    is_blocking=True,
                    title_tr="Metodoloji veya Kadans Tanımı Eksik",
                    title_en="Methodology or Cadence Undefined",
                    explanation_tr="Araştırma kategorisi veya zaman kadansı eksik olduğundan yöntem uyumu doğrulanamıyor.",
                    explanation_en="Missing methodology category or sampling cadence prevents compatibility audit.",
                    supporting_evidence=f"Category: '{cat}', Cadence: '{cadence}'",
                    suggested_research_action_tr="Metodoloji kategorisini ve zaman kadansını belirleyin.",
                    suggested_research_action_en="Specify standardized methodology category and cadence.",
                    resolution_criteria_tr="Kayıtlı spesifikasyon ile kadansın tanımlanması.",
                    resolution_criteria_en="Registered specification and defined sampling cadence.",
                )
            )

        # 8. MISSING_INDEPENDENT_REPLICATION
        rep_status = getattr(record, "replication_verdict", "REPLICATION_NOT_ESTABLISHED")
        if rep_status != "INDEPENDENT_REPLICATION_CONFIRMED":
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-08",
                    record_id=rec_id,
                    gap_category=GapCategory.MISSING_INDEPENDENT_REPLICATION.value,
                    severity=GapSeverity.HIGH.value,
                    is_blocking=False,
                    title_tr="Bağımsız Replikasyon Henüz Gerçekleştirilmedi",
                    title_en="Independent Replication Not Yet Established",
                    explanation_tr="Mevcut bulgular tek bir araştırma sürecine aittir; harici bağımsız replikasyon bulunmuyor.",
                    explanation_en="Findings stem from a single research procedure; no independent replication exists.",
                    supporting_evidence=f"Replication status: {rep_status}",
                    suggested_research_action_tr="Farklı bir piyasa rejimi veya bağımsız analist ile doğrulama çalışması yürütün.",
                    suggested_research_action_en="Conduct out-of-sample replication with independent methodology.",
                    resolution_criteria_tr="Bağımsız replikasyon raporunun kanıt kütüphanesine kaydedilmesi.",
                    resolution_criteria_en="Independent replication report recorded in evidence library.",
                )
            )

        # 9. CONFLICTING_RESEARCH_FINDINGS
        direction_match = getattr(record, "direction_match", None)
        if direction_match is False:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-09",
                    record_id=rec_id,
                    gap_category=GapCategory.CONFLICTING_RESEARCH_FINDINGS.value,
                    severity=GapSeverity.MEDIUM.value,
                    is_blocking=False,
                    title_tr="Çelişkili veya Tutarsız Yönsel İstatistikler",
                    title_en="Conflicting or Inconsistent Directional Statistics",
                    explanation_tr="Araştırma verisi holdout ve in-sample arasında yönsel uyumsuzluk gösteriyor.",
                    explanation_en="Research data shows directional conflict between holdout and in-sample.",
                    supporting_evidence="direction_match is False",
                    suggested_research_action_tr="Holdout ayrımını yeniden yapılandırın ve rejim kaymasını inceleyin.",
                    suggested_research_action_en="Re-evaluate holdout partition and inspect regime drift.",
                    resolution_criteria_tr="Yönsel istatistiklerin uzlaştırılması ve gerekçelendirilmesi.",
                    resolution_criteria_en="Reconciliation and justification of directional metrics.",
                )
            )

        # 10. UNSUPPORTED_STATISTICAL_CLAIM
        p_val = getattr(record, "raw_p_value", None)
        if p_val is not None and p_val > 0.05:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-10",
                    record_id=rec_id,
                    gap_category=GapCategory.UNSUPPORTED_STATISTICAL_CLAIM.value,
                    severity=GapSeverity.HIGH.value,
                    is_blocking=False,
                    title_tr=f"İstatistiki Olarak Anlamsız Sonuç (p = {p_val:.3f} > 0.05)",
                    title_en=f"Statistically Insignificant Result (p = {p_val:.3f} > 0.05)",
                    explanation_tr=f"Hesaplanan p-değeri ({p_val:.3f}) standart %5 anlamlılık düzeyini sağlayamıyor.",
                    explanation_en=f"Calculated p-value ({p_val:.3f}) fails the standard 5% significance threshold.",
                    supporting_evidence=f"p_value: {p_val}",
                    suggested_research_action_tr="Boş hipotezin reddedilemediğini raporlayın; tahmin iddiasında bulunmayın.",
                    suggested_research_action_en="Report failure to reject null hypothesis; avoid predictive claims.",
                    resolution_criteria_tr="Çalışmanın tanımlayıcı (descriptive) olarak etiketlenmesi.",
                    resolution_criteria_en="Classification of the finding as descriptive-only.",
                )
            )

        # 11. SUPERSEDED_EVIDENCE
        if att and isinstance(att, dict) and att.get("is_superseded"):
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-11",
                    record_id=rec_id,
                    gap_category=GapCategory.SUPERSEDED_EVIDENCE.value,
                    severity=GapSeverity.HIGH.value,
                    is_blocking=True,
                    title_tr="Yürürlükten Kaldırılmış Tasdik / Kanıt",
                    title_en="Superseded Evidence / Attestation",
                    explanation_tr="Bu kaydın tasdik belgesi yeni bir politika veya düzeltme ile geçersiz kılınmıştır.",
                    explanation_en="The attestation for this record was superseded by a newer policy or correction.",
                    supporting_evidence="is_superseded: True",
                    suggested_research_action_tr="Güncel tasdik belgesini temin edin.",
                    suggested_research_action_en="Obtain active, non-superseded attestation.",
                    resolution_criteria_tr="Yeni geçerli tasdik eklenmesi.",
                    resolution_criteria_en="Attachment of current active attestation.",
                )
            )

        # 12. EXPIRED_ATTESTATION
        if att and isinstance(att, dict):
            exp_utc = att.get("expires_at_utc")
            if exp_utc:
                try:
                    exp_dt = datetime.fromisoformat(exp_utc.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        gaps.append(
                            EvidenceGap(
                                gap_id=f"GAP-{rec_id}-12",
                                record_id=rec_id,
                                gap_category=GapCategory.EXPIRED_ATTESTATION.value,
                                severity=GapSeverity.HIGH.value,
                                is_blocking=True,
                                title_tr=f"Tasdik Süresi Dolmuş ({exp_utc})",
                                title_en=f"Attestation Expired ({exp_utc})",
                                explanation_tr=f"Tasdiğin geçerlilik süresi {exp_utc} tarihinde dolmuştur.",
                                explanation_en=f"Attestation validity expired on {exp_utc}.",
                                supporting_evidence=f"Expiry: {exp_utc}",
                                suggested_research_action_tr="Yetkili makamdan güncel tasdik talep edin.",
                                suggested_research_action_en="Request updated attestation from authority.",
                                resolution_criteria_tr="Gelecek tarihli geçerli tasdik temini.",
                                resolution_criteria_en="Provision of active unexpired attestation.",
                            )
                        )
                except Exception:
                    pass

        # 13. MISSING_REPRODUCIBILITY_INSTRUCTIONS
        if not src_path or not Path(src_path).exists():
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-13",
                    record_id=rec_id,
                    gap_category=GapCategory.MISSING_REPRODUCIBILITY_INSTRUCTIONS.value,
                    severity=GapSeverity.MEDIUM.value,
                    is_blocking=True,
                    title_tr="Çevrimdışı Tekrarlanabilirlik Protokolü Eksik",
                    title_en="Missing Offline Reproducibility Protocol",
                    explanation_tr="Araştırmanın bağımsız olarak yeniden çalıştırılabilmesi için gerekli girdi paketi eksik.",
                    explanation_en="Missing input bundle required for independent execution of procedure.",
                    supporting_evidence="Source artifact unavailable for local reproduction.",
                    suggested_research_action_tr="Çevrimdışı çalıştırılabilir veri ve parametre paketini kaydedin.",
                    suggested_research_action_en="Package offline executable dataset slice and parameters.",
                    resolution_criteria_tr="Reproducibility Lab ile başarılı yeniden çalıştırma.",
                    resolution_criteria_en="Successful local execution in Reproducibility Lab.",
                )
            )

        # 14. MISSING_GOVERNANCE_APPROVAL
        if GOVERNANCE_DECISION != "TECHNICAL_NO_GO" or not CBE_TRADING_DISABLED:
            gaps.append(
                EvidenceGap(
                    gap_id=f"GAP-{rec_id}-14",
                    record_id=rec_id,
                    gap_category=GapCategory.MISSING_GOVERNANCE_APPROVAL.value,
                    severity=GapSeverity.CRITICAL.value,
                    is_blocking=True,
                    title_tr="Yönetişim Güvenlik İhlali Saptandı",
                    title_en="Governance Security Violation Detected",
                    explanation_tr="Sistem dondurma kararı ihlal edilmiş görünüyor; fail-closed kuralı devreye girmelidir.",
                    explanation_en="System freeze decision appears breached; fail-closed rule must engage.",
                    supporting_evidence=f"Governance: {GOVERNANCE_DECISION}, Trading: {CBE_TRADING_DISABLED}",
                    suggested_research_action_tr="TECHNICAL_NO_GO ve CBE_TRADING_DISABLED durumunu derhal teyit edin.",
                    suggested_research_action_en="Confirm TECHNICAL_NO_GO and trading prohibition immediately.",
                    resolution_criteria_tr="Yönetişim değişmezlerinin doğrulanması.",
                    resolution_criteria_en="Verification of canonical governance invariants.",
                )
            )

        return gaps

    @classmethod
    def analyze_catalog(cls, catalog_records: List[Any]) -> Dict[str, Any]:
        """
        Analyzes all records in catalog, returning aggregated gap statistics,
        critical blocking gaps, and categorized gap summaries.
        """
        all_gaps: List[EvidenceGap] = []
        for rec in catalog_records:
            all_gaps.extend(cls.analyze_record(rec))

        critical_gaps = [g for g in all_gaps if g.severity == GapSeverity.CRITICAL.value]
        high_gaps = [g for g in all_gaps if g.severity == GapSeverity.HIGH.value]
        medium_gaps = [g for g in all_gaps if g.severity == GapSeverity.MEDIUM.value]
        low_gaps = [g for g in all_gaps if g.severity == GapSeverity.LOW.value]
        blocking_gaps = [g for g in all_gaps if g.is_blocking]

        # Group by category
        by_category: Dict[str, int] = {}
        for g in all_gaps:
            by_category[g.gap_category] = by_category.get(g.gap_category, 0) + 1

        return {
            "total_gaps": len(all_gaps),
            "critical_count": len(critical_gaps),
            "high_count": len(high_gaps),
            "medium_count": len(medium_gaps),
            "low_count": len(low_gaps),
            "blocking_count": len(blocking_gaps),
            "category_breakdown": by_category,
            "gaps": [g.to_dict() for g in all_gaps],
        }


# Global analyzer instance
evidence_gap_analyzer = EvidenceGapAnalyzer()
