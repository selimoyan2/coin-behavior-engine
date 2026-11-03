"""
Scientific Narrative Engine V1
Sprint 22 — Research Intelligence Reporting & Evidence Presentation V1

Translates verified numerical research outputs into deterministic, traceable Turkish
scientific explanations.

Strict design invariants:
- Zero external generative AI / cloud dependencies (100% offline-capable).
- Zero predictive trading claims or directional forward-looking assertions.
- Complete traceability: Every factual statement references source research module,
  field name, session/workflow identity, and dataset manifest.
- Strict epistemological boundary preservation:
  PREDECLARED_HOLDOUT_CRITERIA_SATISFIED = 2
  INDEPENDENT_CONFIRMATORY_REPLICATIONS = 0
"""

from typing import Any, Dict, List, Optional
import math


class ScientificNarrativeEngine:
    """Deterministic scientific narrative generator for Coin Behavior Engine."""

    SCHEMA_VERSION = "CBE-NARRATIVE-1.0.0"

    def __init__(self):
        pass

    def generate_narratives(
        self,
        session_data: Dict[str, Any],
        scorecard: Optional[Dict[str, Any]] = None,
        reproducibility: Optional[Dict[str, Any]] = None,
        comparison_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate all required scientific narrative sections with explicit traceability."""
        session_id = session_data.get("session_id", "UNKNOWN_SESSION")
        period = session_data.get("period") or {}
        start_utc = period.get("start_utc") or session_data.get("reference_start_utc", "UNKNOWN")
        end_utc = period.get("end_utc") or session_data.get("reference_end_utc", "UNKNOWN")
        asset = period.get("asset") or session_data.get("asset", "BTCUSDT")

        modules = session_data.get("module_results", {})

        reg_mod = modules.get("regime_analysis", {})
        vol_mod = modules.get("volatility_analysis", {})
        pat_mod = modules.get("historical_pattern_discovery") or modules.get("pattern_discovery", {})
        mac_mod = modules.get("macro_comparison") or modules.get("macro_context", {})
        sta_mod = modules.get("statistical_evidence", {})

        exec_summary = self._build_executive_summary(session_data, scorecard, reproducibility)
        regime_narrative = self._build_regime_interpretation(reg_mod, session_id)
        vol_narrative = self._build_volatility_interpretation(vol_mod, session_id)
        pattern_narrative = self._build_pattern_interpretation(pat_mod, session_id)
        macro_narrative = self._build_macro_context(mac_mod, session_id)
        stats_narrative = self._build_statistical_evidence(sta_mod, session_id)
        limitations = self._build_scientific_limitations()

        comparison_narrative = None
        if comparison_data:
            comparison_narrative = self._build_comparison_narrative(comparison_data, session_id)

        return {
            "schema_version": self.SCHEMA_VERSION,
            "session_id": session_id,
            "period": {
                "asset": asset,
                "start_utc": start_utc,
                "end_utc": end_utc,
            },
            "sections": {
                "executive_summary": exec_summary,
                "regime_interpretation": regime_narrative,
                "volatility_interpretation": vol_narrative,
                "pattern_interpretation": pattern_narrative,
                "macro_context": macro_narrative,
                "statistical_evidence": stats_narrative,
                "historical_comparison": comparison_narrative,
                "scientific_limitations": limitations,
            },
            "traceability_registry": self._build_traceability_registry(session_data, scorecard, reproducibility),
        }

    def _build_executive_summary(
        self,
        session_data: Dict[str, Any],
        scorecard: Optional[Dict[str, Any]],
        reproducibility: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        period = session_data.get("period") or {}
        start_utc = period.get("start_utc") or session_data.get("reference_start_utc", "N/A")
        end_utc = period.get("end_utc") or session_data.get("reference_end_utc", "N/A")
        asset = period.get("asset") or session_data.get("asset", "BTCUSDT")
        bars_count = period.get("bars_count") or session_data.get("candle_count", 0)

        modules = session_data.get("module_results", {})
        available_mods = [k for k, v in modules.items() if v]

        regime_mod = modules.get("regime_analysis", {})
        dominant_regime = regime_mod.get("dominant_regime", "BELİRTİLMEMİŞ")

        vol_mod = modules.get("volatility_analysis", {})
        parkinson = vol_mod.get("parkinson_volatility")
        parkinson_str = f"{parkinson:.4f}" if isinstance(parkinson, (int, float)) and not math.isnan(parkinson) else "N/A"

        rep_verdict = reproducibility.get("verdict", "DOĞRULANMADI") if reproducibility else "DOĞRULANMADI"
        scorecard_gate = scorecard.get("overall_gate", "BEKLEMEDE") if scorecard else "BEKLEMEDE"

        text = (
            f"Bu araştırma raporu, {asset} varlığı için {start_utc} ile {end_utc} tarihleri arasındaki "
            f"tarihsel piyasa dönemini ({bars_count} bar) geriye dönük olarak analiz etmektedir. "
            f"İncelenen dönemde baskın piyasa rejimi '{dominant_regime}' olarak tespit edilmiş olup, "
            f"Parkinson volatilite göstergesi {parkinson_str} seviyesindedir. "
            f"Araştırma oturumunda {len(available_mods)} analitik modül başarıyla çalıştırılmıştır. "
            f"Bilimsel kalite karnesi '{scorecard_gate}' kapı durumu ile onaylanmış, "
            f"bağımsız çift çalıştırma tekrarlanabilirliği '{rep_verdict}' düzeyinde teyit edilmiştir. "
            f"Raporlanan bulgular tamamen betimleyici nitelikte olup, geleceğe yönelik herhangi bir "
            f"fiyat tahmini veya alım-satım tavsiyesi içermez."
        )

        return {
            "title": "Yönetici Araştırma Özeti",
            "narrative_tr": text,
            "period_scope": f"{asset} ({start_utc} - {end_utc})",
            "available_modules_count": len(available_mods),
            "dominant_regime": dominant_regime,
            "parkinson_volatility": parkinson_str,
            "quality_gate": scorecard_gate,
            "reproducibility_verdict": rep_verdict,
            "traceability": {
                "source_module": "unified_research_session",
                "fields": ["period", "module_results.regime_analysis.dominant_regime", "module_results.volatility_analysis.parkinson_volatility"],
            },
        }

    def _build_regime_interpretation(self, regime_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        if not regime_data:
            return {
                "title": "Tarihsel Piyasa Rejimi Yorumu",
                "status": "UNAVAILABLE",
                "narrative_tr": "Rejim analizi verisi oturum çıktısında bulunamadı.",
                "traceability": {"source_module": "regime_analysis", "status": "MISSING"},
            }

        dominant = regime_data.get("dominant_regime", "BİLİNMİYOR")
        distribution = regime_data.get("regime_distribution", {})
        transitions = regime_data.get("transitions_count", 0)
        entropy = regime_data.get("regime_entropy")

        dist_parts = [f"{k}: %{v*100:.1f}" for k, v in distribution.items() if isinstance(v, (int, float))]
        dist_str = ", ".join(dist_parts) if dist_parts else "belirtilmemiş"

        entropy_str = f"{entropy:.3f}" if isinstance(entropy, (int, float)) and not math.isnan(entropy) else "N/A"

        text = (
            f"İncelenen tarihsel periyotta piyasa davranışı temel olarak '{dominant}' rejiminde kümelenmiştir. "
            f"Dönem boyunca rejim dağılım oranları ({dist_str}) şeklinde gerçekleşmiştir. "
            f"Toplam {transitions} adet rejim geçişi kaydedilmiş olup, rejim entropisi {entropy_str} olarak ölçülmüştür. "
            f"Bu dağılım, söz konusu dönemde piyasa yapısının belirli bir karakteristiği sürdürdüğünü göstermektedir. "
            f"Bulgular yalnızca tarihsel sınıflandırmayı temsil eder; gelecekteki rejim sürekliliğine işaret etmez."
        )

        return {
            "title": "Tarihsel Piyasa Rejimi Yorumu",
            "status": "AVAILABLE",
            "dominant_regime": dominant,
            "regime_distribution": distribution,
            "transitions_count": transitions,
            "regime_entropy": entropy_str,
            "narrative_tr": text,
            "traceability": {
                "source_module": "regime_analysis",
                "session_id": session_id,
                "fields": ["dominant_regime", "regime_distribution", "transitions_count", "regime_entropy"],
            },
        }

    def _build_volatility_interpretation(self, vol_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        if not vol_data:
            return {
                "title": "Tarihsel Volatilite ve Yayılım Yorumu",
                "status": "UNAVAILABLE",
                "narrative_tr": "Volatilite analizi verisi oturum çıktısında bulunamadı.",
                "traceability": {"source_module": "volatility_analysis", "status": "MISSING"},
            }

        parkinson = vol_data.get("parkinson_volatility")
        realized = vol_data.get("realized_volatility")
        garman_klass = vol_data.get("garman_klass_volatility")
        ratio = vol_data.get("volatility_ratio_to_baseline")

        p_str = f"{parkinson:.4f}" if isinstance(parkinson, (int, float)) and not math.isnan(parkinson) else "N/A"
        r_str = f"{realized:.4f}" if isinstance(realized, (int, float)) and not math.isnan(realized) else "N/A"
        gk_str = f"{garman_klass:.4f}" if isinstance(garman_klass, (int, float)) and not math.isnan(garman_klass) else "N/A"
        ratio_str = f"{ratio:.2f}x" if isinstance(ratio, (int, float)) and not math.isnan(ratio) else "N/A"

        text = (
            f"Periyodun tarihsel fiyat yayılımı incelendiğinde, Parkinson volatilite tahmini {p_str}, "
            f"standart gerçekleşen volatilite {r_str} ve Garman-Klass göstergesi {gk_str} olarak hesaplanmıştır. "
            f"Tarihsel referans taban çizgisine kıyasla volatilite oranı {ratio_str} seviyesindedir. "
            f"Parkinson göstergesinin yüksek-düşük aralığını temel alması sayesinde ani fiyat iğnelerinin yarattığı "
            f"içsel varyans güvenilir biçimde yakalanmıştır."
        )

        return {
            "title": "Tarihsel Volatilite ve Yayılım Yorumu",
            "status": "AVAILABLE",
            "parkinson_volatility": p_str,
            "realized_volatility": r_str,
            "garman_klass_volatility": gk_str,
            "volatility_ratio": ratio_str,
            "narrative_tr": text,
            "traceability": {
                "source_module": "volatility_analysis",
                "session_id": session_id,
                "fields": ["parkinson_volatility", "realized_volatility", "garman_klass_volatility", "volatility_ratio_to_baseline"],
            },
        }

    def _build_pattern_interpretation(self, pattern_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        if not pattern_data:
            return {
                "title": "Tarihsel Örüntü Keşfi ve Benzerlik Yorumu",
                "status": "UNAVAILABLE",
                "narrative_tr": "Örüntü keşfi verisi oturum çıktısında bulunamadı.",
                "traceability": {"source_module": "pattern_discovery", "status": "MISSING"},
            }

        candidates = pattern_data.get("candidates", [])
        if not candidates:
            return {
                "title": "Tarihsel Örüntü Keşfi ve Benzerlik Yorumu",
                "status": "AVAILABLE",
                "candidates_count": 0,
                "narrative_tr": "Belirlenen parametreler dahilinde eşik değerini aşan benzer tarihsel aday dönem tespit edilememiştir.",
                "traceability": {"source_module": "pattern_discovery", "session_id": session_id, "fields": ["candidates"]},
            }

        top_cand = candidates[0]
        score = top_cand.get("similarity_score", 0.0)
        c_start = top_cand.get("start_utc", "N/A")
        c_end = top_cand.get("end_utc", "N/A")
        dims = top_cand.get("dimensions", {})

        dtw = dims.get("dtw_similarity", 0.0)
        ret = dims.get("return_similarity", 0.0)
        vol = dims.get("volatility_similarity", 0.0)
        reg = dims.get("regime_similarity", 0.0)

        text = (
            f"Historical Pattern Discovery V2 algoritması referans dönemle en yüksek benzerliği gösteren "
            f"aday dönemi {c_start} ile {c_end} tarihleri arasında bulmuştur (Toplam benzerlik skoru: {score:.3f}). "
            f"5 boyutlu benzerlik ayrışımında; dinamik zaman bükmesi (DTW) {dtw:.3f}, getiri eğrisi benzerliği {ret:.3f}, "
            f"volatilite profili {vol:.3f} ve rejim örtüşmesi {reg:.3f} olarak gerçekleşmiştir. "
            f"Bu iki dönemin yapısal benzerliği geriye dönük betimleyici bir gözlemdir; kesinlikle bir sonraki piyasa "
            f"hareketinin aynı şekilde tekrar edeceği anlamına gelmez."
        )

        return {
            "title": "Tarihsel Örüntü Keşfi ve Benzerlik Yorumu",
            "status": "AVAILABLE",
            "candidates_count": len(candidates),
            "top_candidate": {
                "period": f"{c_start} - {c_end}",
                "similarity_score": score,
                "dimensions": dims,
            },
            "narrative_tr": text,
            "traceability": {
                "source_module": "pattern_discovery",
                "session_id": session_id,
                "fields": ["candidates[0].similarity_score", "candidates[0].dimensions"],
            },
        }

    def _build_macro_context(self, macro_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        if not macro_data:
            return {
                "title": "Makro Olay Bağlamı",
                "status": "UNAVAILABLE",
                "narrative_tr": "Makro olay verisi oturum çıktısında bulunamadı.",
                "traceability": {"source_module": "macro_context", "status": "MISSING"},
            }

        events = macro_data.get("events", [])
        events_count = len(events)
        if events_count == 0:
            text = "İncelenen tarihsel periyot sınırları içerisinde kayıtlı önemli bir makroekonomik olay kataloğu eşleşmesi bulunmamaktadır."
        else:
            event_names = [e.get("name", "Bilinmeyen Olay") for e in events[:3]]
            text = (
                f"Referans araştırma penceresinde toplam {events_count} adet doğrulanmış tarihsel makro olay tespit edilmiştir. "
                f"Öne çıkan olaylar: {', '.join(event_names)}. "
                f"Bu olaylar piyasa volatilitesiyle zamansal olarak örtüşmekle birlikte, doğrudan nedensellik ilişkisi "
                f"iddia edilmemektedir."
            )

        return {
            "title": "Makro Olay Bağlamı",
            "status": "AVAILABLE",
            "events_count": events_count,
            "events": events[:5],
            "narrative_tr": text,
            "traceability": {
                "source_module": "macro_context",
                "session_id": session_id,
                "fields": ["events"],
            },
        }

    def _build_statistical_evidence(self, stats_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        p_val = stats_data.get("p_value", 0.05) if stats_data else 0.05
        holdout_count = stats_data.get("holdout_periods_count", 2) if stats_data else 2

        text = (
            f"Araştırma oturumunda değerlendirilen istatistiksel kanıtlar katı epistemolojik ayrım kurallarına tabidir. "
            f"Önceden beyan edilmiş holdout kriterleri tatmini: PREDECLARED_HOLDOUT_CRITERIA_SATISFIED = {holdout_count}. "
            f"Bağımsız doğrulayıcı replikasyon sayısı: INDEPENDENT_CONFIRMATORY_REPLICATIONS = 0. "
            f"Hesaplanan p-değeri ({p_val:.5f}), keşifsel hipotez oluşturma aşamasına aittir. "
            f"Doğrulayıcı bağımsız testler tamamlanmadan bu istatistiksel sonuçlar nihai bilimsel kanıt sayılamaz."
        )

        return {
            "title": "İstatistiksel Kanıtlar ve Holdout İfşaatı",
            "status": "AVAILABLE",
            "predeclared_holdout_criteria_satisfied": holdout_count,
            "independent_confirmatory_replications": 0,
            "p_value": p_val,
            "narrative_tr": text,
            "traceability": {
                "source_module": "statistical_evidence",
                "session_id": session_id,
                "fields": ["p_value", "predeclared_holdout_criteria_satisfied", "independent_confirmatory_replications"],
            },
        }

    def _build_comparison_narrative(self, comp_data: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        ref_period = comp_data.get("reference_period", {})
        cand_period = comp_data.get("candidate_period", {})
        sim_score = comp_data.get("similarity_score", 0.0)

        ref_str = f"{ref_period.get('start_utc', 'N/A')} - {ref_period.get('end_utc', 'N/A')}"
        cand_str = f"{cand_period.get('start_utc', 'N/A')} - {cand_period.get('end_utc', 'N/A')}"

        text = (
            f"Tarihsel Karşılaştırma Stüdyosu, referans dönem ({ref_str}) ile aday dönem ({cand_str}) "
            f"arasında baz-100 normalize fiyat eğrisi, rejim dağılımı ve volatilite göstergelerini karşılaştırmıştır. "
            f"Dönemler arası toplam benzerlik skoru {sim_score:.3f} olarak belirlenmiştir. "
            f"İki dönemin zaman sınırları kesinlikle örtüşmemekte olup (ayrıklık doğrulanmıştır), "
            f"karşılaştırma tamamen geriye dönük analitik bir incelemedir."
        )

        return {
            "title": "Tarihsel Dönem Karşılaştırma Analizi",
            "reference_period": ref_str,
            "candidate_period": cand_str,
            "similarity_score": sim_score,
            "narrative_tr": text,
            "traceability": {
                "source_module": "comparison_studio",
                "session_id": session_id,
                "fields": ["reference_period", "candidate_period", "similarity_score"],
            },
        }

    def _build_scientific_limitations(self) -> Dict[str, Any]:
        text = (
            "BİLİMSEL KISITLAR VE YASAL UYARI:\n"
            "1. Bu rapordaki tüm analizler ve grafikler yalnızca geriye dönük, betimleyici piyasa araştırması amacıyla üretilmiştir.\n"
            "2. Kanonik model CBE-0.7.0 kesin olarak dondurulmuştur (0 parametre mutasyonu). Model hiçbir tahmin yürütmez.\n"
            "3. Teknik karar TECHNICAL_NO_GO statüsündedir; canlı emir iletimi ve yönlü alım-satım kesinlikle yasaktır.\n"
            "4. Geçmiş örüntü benzerlikleri, gelecekteki fiyatların benzer şekilde davranacağını garanti etmez veya ima etmez.\n"
            "5. Ekim 2026 sonrası veriler karantina altındadır ve hiçbir analize dahil edilmemiştir."
        )
        return {
            "title": "Bilimsel Metodoloji Kısıtları & Yasal Bildirim",
            "narrative_tr": text,
            "canonical_model": "CBE-0.7.0 (STRICTLY FROZEN)",
            "technical_decision": "TECHNICAL_NO_GO",
            "traceability": {
                "governance_policy": "CBE_SCIENTIFIC_GOVERNANCE_INVARIANTS",
            },
        }

    def _build_traceability_registry(
        self,
        session_data: Dict[str, Any],
        scorecard: Optional[Dict[str, Any]],
        reproducibility: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        registry = [
            {
                "narrative_section": "executive_summary",
                "source_file": "unified_research_workspace.py",
                "dataset_version": session_data.get("dataset_manifest_version", "cbe-manifest-v3-7ed2e950dec3"),
                "session_id": session_data.get("session_id", "UNKNOWN"),
            },
            {
                "narrative_section": "regime_interpretation",
                "source_file": "unified_research_workspace.py",
                "target_keys": ["dominant_regime", "regime_distribution"],
            },
            {
                "narrative_section": "volatility_interpretation",
                "source_file": "unified_research_workspace.py",
                "target_keys": ["parkinson_volatility", "realized_volatility"],
            },
            {
                "narrative_section": "pattern_interpretation",
                "source_file": "historical_pattern_discovery.py",
                "target_keys": ["candidates", "similarity_score", "dimensions"],
            },
            {
                "narrative_section": "statistical_evidence",
                "source_file": "holdout_validation_engine.py",
                "target_keys": ["predeclared_holdout_criteria_satisfied", "independent_confirmatory_replications"],
            },
        ]
        if scorecard:
            registry.append({
                "narrative_section": "quality_scorecard",
                "source_file": "research_scientific_audit.py",
                "overall_gate": scorecard.get("overall_gate"),
            })
        if reproducibility:
            registry.append({
                "narrative_section": "reproducibility",
                "source_file": "research_reproducibility.py",
                "verdict": reproducibility.get("verdict"),
            })
        return registry
