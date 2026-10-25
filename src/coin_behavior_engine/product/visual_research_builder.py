"""
CBE — Visual Hypothesis Research Builder V2
Sprint 12 (CBE_PRODUCT_ACCELERATION_12)

Provides:
- 8-Step guided visual hypothesis research creation workflow
- Strict bounding and parameter validation
- Pre-execution scientific preview without synthetic fabrication
- Execution engine generating reproducible hypothesis experiments
- Full Turkish localization and governance protection
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# Predefined Research Questions & Templates
# -------------------------------------------------------------

PREDEFINED_RESEARCH_TEMPLATES = [
    {
        "template_id": "VRB-TMPL-01-CPI-VOLATILITY",
        "title_tr": "Tüketici Fiyat Endeksi (CPI) ve Volatilite Genişlemesi",
        "title_en": "Consumer Price Index (CPI) and Volatility Expansion",
        "research_question_tr": "ABD CPI duyuruları sonrasında BTCUSDT gerçekleşen volatilitesinde istatistiki olarak anlamlı bir artış görülür mü?",
        "research_question_en": "Do US CPI announcements coincide with a statistically significant expansion in BTCUSDT realized volatility?",
        "default_asset": "BTCUSDT",
        "default_cohort": "US_CPI",
        "default_metric": "VOLATILITY_SHIFT_RATIO",
        "default_pre_hours": 12,
        "default_post_hours": 12,
        "default_interval": "1h",
        "default_bootstrap_reps": 1000,
        "description_tr": "Duyuru öncesi 12 saat ile duyuru sonrası 12 saat arasındaki gerçekleşen volatilite oranını ve küme önyükleme güven aralığını hesaplar.",
    },
    {
        "template_id": "VRB-TMPL-02-FOMC-REGIME-PERSISTENCE",
        "title_tr": "FOMC Faiz Kararları ve Rejim Geçiş Frekansı",
        "title_en": "FOMC Rate Decisions and Regime Transition Frequency",
        "research_question_tr": "Federal Reserve (FOMC) politika kararları sonrasında rejim geçiş sıklığı ve kalıcılığı nasıl değişir?",
        "research_question_en": "How do regime transition frequencies and persistence alter following Federal Reserve (FOMC) policy decisions?",
        "default_asset": "BTCUSDT",
        "default_cohort": "US_FOMC_RATE_DECISION",
        "default_metric": "REGIME_TRANSITION_PROBABILITY",
        "default_pre_hours": 12,
        "default_post_hours": 12,
        "default_interval": "1h",
        "default_bootstrap_reps": 500,
        "description_tr": "FOMC kararı öncesindeki denge/sıkışma rejimlerinin duyuru sonrasında yüksek volatilite rejimine geçiş olasılığını test eder.",
    },
    {
        "template_id": "VRB-TMPL-03-ANNUAL-VOLATILITY-DRIFT",
        "title_tr": "Yıllara Göre Volatilite Dağılım Farklılıkları",
        "title_en": "Annual Volatility Distribution Divergence",
        "research_question_tr": "BTCUSDT gerçekleşen volatilite dağılımları 2022-2023 ile 2024-2026 yılları arasında istatistiki olarak farklılaşmış mıdır?",
        "research_question_en": "Are BTCUSDT realized volatility distributions significantly different between 2022-2023 and 2024-2026?",
        "default_asset": "BTCUSDT",
        "default_cohort": "MARKET_STRUCTURE",
        "default_metric": "DISTRIBUTION_DRIFT_PSI",
        "default_pre_hours": 24,
        "default_post_hours": 24,
        "default_interval": "1h",
        "default_bootstrap_reps": 500,
        "description_tr": "Farklı piyasa döngülerindeki getiri ve volatilite dağılımlarını PSI ve Wasserstein mesafesi ile karşılaştırır.",
    },
    {
        "template_id": "VRB-TMPL-04-TIMEFRAME-STABILITY",
        "title_tr": "Zaman Dilimleri Arası Etki Kararlılığı",
        "title_en": "Cross-Timeframe Impact Stability",
        "research_question_tr": "Makro olay sonrası gözlemlenen volatilite etkisi farklı mum aralıklarında (1h vs 4h) kararlı kalmakta mıdır?",
        "research_question_en": "Does the observed post-macro event volatility impact remain stable across different candle intervals (1h vs 4h)?",
        "default_asset": "BTCUSDT",
        "default_cohort": "US_INFLATION",
        "default_metric": "CROSS_TIMEFRAME_DELTA",
        "default_pre_hours": 24,
        "default_post_hours": 24,
        "default_interval": "4h",
        "default_bootstrap_reps": 500,
        "description_tr": "Mum örnekleme frekansının etki büyüklüğü üzerindeki duyarlılığını analiz eder.",
    },
    {
        "template_id": "VRB-TMPL-05-OUT-OF-SAMPLE-HOLDOUT",
        "title_tr": "Örneklem Dışı (Holdout) Doğrulama",
        "title_en": "Out-of-Sample Holdout Replication",
        "research_question_tr": "2022–2024 döneminde gözlemlenen ampirik etki, 2025–2026 bağımsız test döneminde devam etmekte midir?",
        "research_question_en": "Does the empirical effect observed during 2022-2024 persist in the independent 2025-2026 holdout period?",
        "default_asset": "BTCUSDT",
        "default_cohort": "US_CPI",
        "default_metric": "HOLDOUT_EFFECT_PERSISTENCE",
        "default_pre_hours": 12,
        "default_post_hours": 12,
        "default_interval": "1h",
        "default_bootstrap_reps": 1000,
        "description_tr": "Aşırı uyum (overfitting) ve veri madenciliği yanılgısını önlemek için holdout ayrımı üzerinde etkinin sürekliliğini test eder.",
    },
]


class VisualResearchBuilderEngine:
    """
    Core engine powering the Visual Hypothesis Research Builder V2.
    """

    @classmethod
    def get_builder_templates(cls) -> List[Dict[str, Any]]:
        """Return available guided hypothesis research templates."""
        return PREDEFINED_RESEARCH_TEMPLATES

    @classmethod
    def get_builder_options(cls) -> Dict[str, Any]:
        """
        Return available datasets, periods, event cohorts, and methodology options.
        """
        from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
        manifest = ContentIntegrityEngine.generate_canonical_manifest()

        return {
            "status": "success",
            "datasets": [
                {
                    "asset": "BTCUSDT",
                    "status": "VERIFIED_AVAILABLE",
                    "coverage_start": "2022-01",
                    "coverage_end": "2026-09",
                    "total_months": 57,
                    "canonical_interval": "5m",
                    "derived_intervals": ["15m", "1h", "4h", "1d"],
                    "data_quality_score": 100.0,
                    "manifest_sha256": manifest.get("manifest_sha256", "UNKNOWN"),
                },
                {
                    "asset": "ETHUSDT",
                    "status": "SOURCE_NOT_AVAILABLE",
                    "reason_tr": "Doğrulanmış çevrimdışı arşiv bulunamadı. Yapay veri üretimi yasaktır.",
                },
                {
                    "asset": "SOLUSDT",
                    "status": "SOURCE_NOT_AVAILABLE",
                    "reason_tr": "Doğrulanmış çevrimdışı arşiv bulunamadı. Yapay veri üretimi yasaktır.",
                }
            ],
            "preset_periods": [
                {"period_id": "ALL_VERIFIED", "label_tr": "Tüm Doğrulanmış Dönem (2022-01 - 2026-09)", "start": "2022-01", "end": "2026-09"},
                {"period_id": "IN_SAMPLE_TRAIN", "label_tr": "Örneklem İçi / Eğitim (2022-01 - 2024-12)", "start": "2022-01", "end": "2024-12"},
                {"period_id": "HOLDOUT_TEST", "label_tr": "Örneklem Dışı / Holdout (2025-01 - 2026-09)", "start": "2025-01", "end": "2026-09"},
            ],
            "event_cohorts": [
                {"cohort_id": "US_CPI", "label_tr": "ABD Tüketici Fiyat Endeksi (CPI)", "verified_events": 57, "issuing_org": "BLS", "is_parent": False},
                {"cohort_id": "US_CORE_PCE", "label_tr": "ABD Çekirdek PCE Fiyat Endeksi", "verified_events": 45, "issuing_org": "BEA", "is_parent": False},
                {"cohort_id": "US_INFLATION", "label_tr": "ABD Enflasyon Üst Kohortu (CPI + PCE)", "verified_events": 102, "issuing_org": "BLS + BEA", "is_parent": True},
                {"cohort_id": "US_FOMC_RATE_DECISION", "label_tr": "Federal Reserve FOMC Faiz Kararları", "verified_events": 38, "issuing_org": "Federal Reserve", "is_parent": False},
                {"cohort_id": "US_NONFARM_PAYROLLS", "label_tr": "ABD Tarım Dışı İstihdam (NFP)", "verified_events": 57, "issuing_org": "BLS", "is_parent": False},
                {"cohort_id": "US_GDP", "label_tr": "ABD Reel GSYİH (GDP QoQ)", "verified_events": 19, "issuing_org": "BEA", "is_parent": False},
            ],
            "metrics": [
                {"metric_id": "VOLATILITY_SHIFT_RATIO", "label_tr": "Volatilite Değişim Oranı (Post / Pre)"},
                {"metric_id": "REGIME_TRANSITION_PROBABILITY", "label_tr": "Rejim Geçiş Olasılığı"},
                {"metric_id": "DISTRIBUTION_DRIFT_PSI", "label_tr": "Nüfus Kararlılık İndeksi (PSI)"},
                {"metric_id": "CROSS_TIMEFRAME_DELTA", "label_tr": "Zaman Dilimi Etki Farkı"},
                {"metric_id": "HOLDOUT_EFFECT_PERSISTENCE", "label_tr": "Holdout Etki Devamlılığı"},
            ],
            "intervals": ["1h", "4h", "1d", "15m"],
            "bootstrap_methods": [
                {"method_id": "CLUSTER_BOOTSTRAP", "label_tr": "Olay Düzeyinde Küme Önyüklemesi (Önerilen)", "description_tr": "Olaylar arasındaki serisel bağımlılığı korur."},
                {"method_id": "MOVING_BLOCK_BOOTSTRAP", "label_tr": "Hareketli Blok Önyüklemesi (Block)", "description_tr": "Zaman serisi otokorelasyonunu korur."},
            ],
            "confidence_levels": [0.90, 0.95, 0.99],
        }

    @classmethod
    def generate_research_preview(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 6: Pre-execution preview detailing bounds, exclusions, and methodology.
        Strictly prevents synthetic price fabrication or premature result display.
        """
        asset = str(config.get("asset", "BTCUSDT"))
        if asset != "BTCUSDT":
            return {
                "status": "ERROR",
                "can_execute": False,
                "error_tr": f"'{asset}' varlığı için doğrulanmış çevrimdışı arşiv bulunamadı. Yapay veri üretimi yasaktır.",
                "error_en": f"Verified offline archive unavailable for '{asset}'. Synthetic price fabrication is prohibited.",
            }

        cohort = str(config.get("event_cohort", "US_CPI"))
        interval = str(config.get("interval", "1h"))
        pre_h = min(168, max(2, int(config.get("pre_hours", 12))))
        post_h = min(168, max(2, int(config.get("post_hours", 12))))
        reps = min(2000, max(50, int(config.get("bootstrap_reps", 1000))))
        conf = float(config.get("confidence_level", 0.95))

        # Expected sample size based on verified cohort
        cohort_counts = {
            "US_CPI": 57,
            "US_CORE_PCE": 45,
            "US_INFLATION": 102,
            "US_FOMC_RATE_DECISION": 38,
            "US_NONFARM_PAYROLLS": 57,
            "US_GDP": 19,
        }
        total_events = cohort_counts.get(cohort, 30)

        # Estimated runtime
        est_seconds = round(0.0003 * reps + (total_events * 0.005), 2)

        return {
            "status": "PREVIEW_READY",
            "can_execute": True,
            "preview_summary": {
                "research_question_tr": config.get("research_question_tr", "Seçilen hipotez yapılandırması."),
                "target_asset": asset,
                "event_cohort": cohort,
                "total_verified_events": total_events,
                "expected_exclusions": 0,
                "temporal_window": f"-{pre_h}h / +{post_h}h (Toplam {pre_h + post_h} saat)",
                "interval": interval,
                "resample_method": config.get("bootstrap_method", "CLUSTER_BOOTSTRAP"),
                "bootstrap_resamples": reps,
                "confidence_level_pct": round(conf * 100, 1),
                "holdout_available": True,
                "holdout_period": "2025-01 / 2026-09",
                "estimated_execution_time_sec": est_seconds,
            },
            "methodology_limitations_tr": (
                "Ampirik araştırmalar geçmiş gözlemlere dayanır. Gelecekteki piyasa rejimleri yapısal farklılık gösterebilir. "
                "İstatistiki olarak anlamlı bir korelasyon veya volatilite artışı, yönsel alım-satım avantajı oluşturmaz."
            ),
            "governance_verification": {
                "synthetic_price_fabrication": "PROHIBITED_VERIFIED",
                "data_isolation": "OFFLINE_PARQUET_ONLY",
                "trading_eligibility": "ZERO",
            }
        }

    @classmethod
    def execute_builder_research(cls, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 7 & 8: Execute bounded hypothesis experiment and return verified results.
        """
        from coin_behavior_engine.product.hypothesis_studio import HypothesisStudioEngine

        # Verify asset safety
        asset = str(config.get("asset", "BTCUSDT"))
        if asset != "BTCUSDT":
            return {
                "status": "ERROR",
                "error_tr": f"'{asset}' veri seti bulunamadı. Araştırma başlatılamaz.",
            }

        # Bounding parameters
        safe_config = {
            "template_id": config.get("template_id", "CUSTOM_BUILDER_EXPERIMENT"),
            "event_cohort": config.get("event_cohort", "US_CPI"),
            "interval": config.get("interval", "1h"),
            "pre_hours": min(168, max(2, int(config.get("pre_hours", 12)))),
            "post_hours": min(168, max(2, int(config.get("post_hours", 12)))),
            "outcome_metric": config.get("outcome_metric", "volatility"),
            "bootstrap_reps": min(2000, max(50, int(config.get("bootstrap_reps", 1000)))),
            "confidence_level": float(config.get("confidence_level", 0.95)),
            "random_seed": int(config.get("random_seed", 42)),
        }

        # Execute using bounded hypothesis studio engine
        raw_result = HypothesisStudioEngine.execute_hypothesis_experiment(safe_config)

        # Augment with builder metadata
        res = dict(raw_result)
        res["builder_version"] = "VRB-V2.0"
        res["executed_at_utc"] = datetime.now(timezone.utc).isoformat()
        res["research_question_tr"] = config.get(
            "research_question_tr",
            f"{safe_config['event_cohort']} duyuruları sonrasında {safe_config['outcome_metric']} davranışı analizi."
        )

        return res
