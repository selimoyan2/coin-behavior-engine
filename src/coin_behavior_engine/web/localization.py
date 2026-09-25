"""Central presentation dictionary and Turkish localization formatters.

Scope: Presentation Layer Only.
Preserves underlying engine constants, model states, and machine-readable API formats.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

# ----------------------------------------------------------------------
# Status & State Translations
# ----------------------------------------------------------------------

STATUS_TRANSLATIONS: Dict[str, str] = {
    "ACTIVE": "AKTİF",
    "COMPLETE": "TAMAMLANDI",
    "MONITORING": "İZLENİYOR",
    "FROZEN": "DONDURULDU",
    "AUDITED": "DENETLENDİ",
    "PASS": "BAŞARILI",
    "FAILED": "BAŞARISIZ",
    "UNKNOWN": "BİLİNMİYOR",
    "PENDING": "BEKLİYOR",
    "MISSING": "EKSİK",
    "STALE": "GÜNCEL DEĞİL",
    "DELAYED": "GECİKMELİ",
    "HEALTHY": "SAĞLIKLI",
    "DEGRADED": "KISMİ SORUN",
    "RUNNING": "ÇALIŞIYOR",
    "STOPPED": "DURDU",
    "IN_PROGRESS": "AKTİF",
    "LIVE_MONITORING": "CANLI İZLEME",
    "DATA_WAITING": "VERİ BEKLENİYOR",
    "INTEGRITY_BREACH": "BÜTÜNLÜK HATASI",
    "NO_RECORDS_YET": "HENÜZ KAYIT YOK",
    "VERIFIED": "DOĞRULANDI",
}

MARKET_STATE_TRANSLATIONS: Dict[str, str] = {
    "QUIET": "SAKİN",
    "COMPRESSION": "SIKIŞMA",
    "NORMAL": "NORMAL",
    "EXPANSION_WATCH": "GENİŞLEME OLASILIĞI",
    "HIGH_VOLATILITY": "YÜKSEK VOLATİLİTE",
    "TAIL_RISK_ELEVATED": "UÇ HAREKET RİSKİ YÜKSEK",
    "JUMP_RISK_ELEVATED": "ANİ HAREKET RİSKİ YÜKSEK",
    "DELEVERAGING_STRESS": "KALDIRAÇ AZALTMA BASKISI",
    "EVENT_SHOCK_ACTIVE": "OLAY KAYNAKLI ŞOK AKTİF",
}

# ----------------------------------------------------------------------
# Presentation UI Copy (Turkish)
# ----------------------------------------------------------------------

UI_COPY_TR: Dict[str, Any] = {
    "app_title": "Coin Behavior Engine",
    "page_title": "Coin Behavior Engine | Canlı İzleme (CBE-0.7.0)",
    "header": {
        "model_frozen": "MODEL DONDURULDU: CBE-0.7.0",
        "audit_pass": "DENETİM: %100 BAŞARILI",
        "live_monitoring": "CANLI İZLEME",
    },
    "cards": {
        "frozen_model": "DONDURULMUŞ MODEL",
        "cutoff_label": "Araştırma Bitiş Zamanı:",
        "phase_a_title": "FAZ A — İLK İLERİYE DÖNÜK GÖZLEM",
        "phase_b_title": "FAZ B — İLERİYE DÖNÜK CANLI GÖZLEM",
        "bars_unit": "Mum",
        "window_label": "Gözlem Aralığı:",
        "integrity_title": "KİLİTLİ KAYIT & DENETİM BÜTÜNLÜĞÜ",
        "breaches_suffix": "İhlal",
    },
    "sprint_table": {
        "title": "Sprint 01–08 Bilimsel Araştırma ve Doğrulama Süreci",
        "headers": {
            "sprint": "SPRINT",
            "info_family": "BİLGİ KATMANI",
            "directional": "DOĞRULANMIŞ YÖN TAHMİNİ?",
            "volatility_risk": "DOĞRULANMIŞ VOLATİLİTE / RİSK BİLGİSİ?",
            "status": "DURUM",
        },
        "rows": [
            {
                "sprint": "Sprint 01 / 01.1",
                "info_family": "Spot Piyasa Yapısı ve Metodoloji",
                "directional": "&#x274C; Doğrulanmadı",
                "volatility_risk": "&#x2705; Doğrulandı (Sıkışma / Genişleme)",
                "status": "AUDITED",
            },
            {
                "sprint": "Sprint 02 / 02.1",
                "info_family": "Tarihsel Benzerlik Analizi",
                "directional": "&#x274C; Doğrulanmadı (Aşırı Uyum)",
                "volatility_risk": "&#x26A0;&#xFE0F; Piyasa Rejimine Bağlı",
                "status": "AUDITED",
            },
            {
                "sprint": "Sprint 03",
                "info_family": "Türev Piyasalar (OI, Basis, Taker, Perp)",
                "directional": "&#x274C; Doğrulanmadı",
                "volatility_risk": "&#x2705; Doğrulandı (Volatilite / Tail Risk Bağlamı)",
                "status": "AUDITED",
            },
            {
                "sprint": "Sprint 04",
                "info_family": "Seans ve Zaman Bağlamı",
                "directional": "&#x274C; Doğrulanmadı",
                "volatility_risk": "&#x2705; Doğrulandı (Gün İçi Volatilite)",
                "status": "AUDITED",
            },
            {
                "sprint": "Sprint 05",
                "info_family": "ETF ve Kurumsal Sermaye Akışları",
                "directional": "&#x274C; Doğrulanmadı (Gecikmeli, Yön Bilgisi Yok)",
                "volatility_risk": "&#x26A0;&#xFE0F; Sınırlı (Bağlamsal / Gecikmeli Bilgi)",
                "status": "AUDITED",
            },
            {
                "sprint": "Sprint 06",
                "info_family": "Haber ve Olay İstihbaratı",
                "directional": "&#x274C; Doğrulanmadı",
                "volatility_risk": "&#x2705; Doğrulandı (Olay Sonrası Volatilite Bağlamı)",
                "status": "AUDITED",
            },
            {
                "sprint": "Sprint 07",
                "info_family": "Birleşik Olasılıksal Motor (CBE-0.7.0)",
                "directional": "&#x274C; Yön Tahmini Kullanılmıyor",
                "volatility_risk": "&#x2705; Kalibre Edilmiş Olasılıksal Durum Motoru",
                "status": "FROZEN",
            },
            {
                "sprint": "Sprint 08",
                "info_family": "İleriye Dönük Doğrulama ve Denetim Kaydı",
                "directional": "&mdash;",
                "volatility_risk": "&#x2705; İleriye Dönük Gözlem ve Değiştirilemez Kayıt",
                "status": "MONITORING",
            },
        ],
    },
    "api_section": {
        "title": "API Uç Noktaları",
        "endpoints": [
            {
                "path": "GET /health",
                "description": "Konteyner sağlık kontrolü (HTTP 200)",
            },
            {
                "path": "GET /api/status",
                "description": "Canlı ileriye dönük motor durumu ve model dondurma doğrulaması",
            },
            {
                "path": "GET /api/metrics",
                "description": "Model kalibrasyonu, Brier skorları ve tahmin ufku istatistikleri",
            },
            {
                "path": "GET /api/analytics/summary",
                "description": "İleriye dönük özet metrikler ve örneklem güvenilirlik sınıfı (?period=all|24h|7d|30d)",
            },
            {
                "path": "GET /api/analytics/horizons",
                "description": "Çoklu tahmin vadeleri hata ve korelasyon metrikleri (MAE, RMSE, Pearson)",
            },
            {
                "path": "GET /api/analytics/calibration",
                "description": "Genişleme olasılığı kalibrasyonu (5-bin) ve tahmin aralığı kapsaması",
            },
            {
                "path": "GET /api/analytics/market-states",
                "description": "Piyasa durumlarına göre olay sonrası oynaklık ve getiri analizi",
            },
            {
                "path": "GET /api/analytics/data-quality",
                "description": "Çalışma zamanı özellik katmanları ve eksik veri durum denetimi",
            },
            {
                "path": "GET /api/analytics/integrity",
                "description": "Kriptografik SHA-256 zinciri ve sistem bütünlüğü denetim sonuçları",
            },
            {
                "path": "GET /api/analytics/timeline",
                "description": "Tarihsel holdout, freeze ve prospective dönem aşamaları zaman çizelgesi",
            },
        ],
    },
    "footer": {
        "uptime_label": "Sunucu Çalışma Süresi:",
        "minutes": "dakika",
        "port": "Port: 8000",
        "platform_note": "Coolify, Docker ve Kubernetes Dağıtımları İçin Tasarlandı",
    },
}

# ----------------------------------------------------------------------
# Formatters
# ----------------------------------------------------------------------


def status_formatter(status: str) -> str:
    """Format technical status code to user-facing Turkish string."""
    if not status:
        return "BİLİNMİYOR"
    key = str(status).upper().strip()
    return STATUS_TRANSLATIONS.get(key, key)


def market_state_formatter(state: str) -> str:
    """Format technical market state enum to user-facing Turkish string."""
    if not state:
        return "BİLİNMİYOR"
    key = str(state).upper().strip()
    return MARKET_STATE_TRANSLATIONS.get(key, key)


def format_number_tr(val: float | int, decimals: int = 1) -> str:
    """Format numeric values using Turkish decimal comma convention."""
    try:
        formatted = f"{float(val):.{decimals}f}"
        return formatted.replace(".", ",")
    except (ValueError, TypeError):
        return str(val)


def parse_iso_utc(iso_str: str) -> datetime | None:
    """Safely parse UTC ISO timestamp."""
    cleaned = iso_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def format_utc_to_turkey_display(iso_str: str) -> str:
    """Convert UTC timestamp string to Turkey Time (UTC+3) with UTC reference."""
    dt = parse_iso_utc(iso_str)
    if not dt:
        return iso_str

    turkey_tz = timezone(timedelta(hours=3))
    dt_tr = dt.astimezone(turkey_tz)
    tr_formatted = dt_tr.strftime("%d.%m.%Y %H:%M")
    utc_formatted = dt.strftime("%H:%M:%S UTC")
    return f"{tr_formatted} TSİ ({utc_formatted})"


def format_time_window_tr(window_str: str) -> str:
    """Format UTC observation window to Turkey Time (UTC+3) with UTC reference.

    Example:
        '2026-09-24T00:00:00Z to 2026-09-24T05:55:00Z'
        -> '24.09.2026 03:00 - 08:55 TSİ (00:00 - 05:55 UTC)'
    """
    if " to " not in window_str:
        return window_str

    parts = window_str.split(" to ")
    dt_start = parse_iso_utc(parts[0])
    dt_end = parse_iso_utc(parts[1])

    if not dt_start or not dt_end:
        return window_str

    turkey_tz = timezone(timedelta(hours=3))
    tr_start = dt_start.astimezone(turkey_tz)
    tr_end = dt_end.astimezone(turkey_tz)

    date_str = tr_start.strftime("%d.%m.%Y")
    tr_interval = f"{tr_start.strftime('%H:%M')} - {tr_end.strftime('%H:%M')} TSİ"
    utc_interval = f"{dt_start.strftime('%H:%M')} - {dt_end.strftime('%H:%M')} UTC"

    return f"{date_str} {tr_interval} ({utc_interval})"
