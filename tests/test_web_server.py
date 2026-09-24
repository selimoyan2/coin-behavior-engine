"""Unit tests for the web monitoring server and Turkish localization."""

from coin_behavior_engine.web.localization import (
    MARKET_STATE_TRANSLATIONS,
    STATUS_TRANSLATIONS,
    UI_COPY_TR,
    format_number_tr,
    format_time_window_tr,
    format_utc_to_turkey_display,
    market_state_formatter,
    status_formatter,
)
from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html


def test_get_engine_state_api_unmodified():
    """Verify that backend state keeps machine-readable English values."""
    state = get_engine_state()
    assert state["engine"] == "Coin Behavior Engine"
    assert state["model_version"] == "CBE-0.7.0"
    assert state["model_status"] == "FROZEN"
    assert "phases" in state
    assert state["phases"]["phase_a"]["status"] == "COMPLETE"
    assert state["phases"]["phase_b"]["status"] == "IN_PROGRESS"
    assert state["integrity"]["lockbox_verified"] is True
    assert state["integrity"]["lookahead_breaches"] == 0
    # Cutoff must be valid UTC ISO
    assert state["historical_cutoff"] == "2026-09-23T23:59:59Z"


def test_status_formatter():
    """Verify status translations match requirements."""
    expected = {
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
    }
    for eng, tr in expected.items():
        assert status_formatter(eng) == tr
        assert STATUS_TRANSLATIONS[eng] == tr


def test_market_state_formatter():
    """Verify market state translations match requirements."""
    expected = {
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
    for eng, tr in expected.items():
        assert market_state_formatter(eng) == tr
        assert MARKET_STATE_TRANSLATIONS[eng] == tr


def test_format_number_tr():
    """Verify Turkish number format with comma."""
    assert format_number_tr(1.25, 2) == "1,25"
    assert format_number_tr(5.4, 1) == "5,4"
    assert format_number_tr(10, 1) == "10,0"


def test_turkey_time_formatting():
    """Verify UTC to Turkey Time (UTC+3) conversion."""
    res = format_utc_to_turkey_display("2026-09-23T23:59:59Z")
    assert "24.09.2026 02:59 TSİ" in res
    assert "(23:59:59 UTC)" in res

    window = format_time_window_tr("2026-09-24T00:00:00Z to 2026-09-24T05:55:00Z")
    assert "24.09.2026 03:00 - 08:55 TSİ" in window
    assert "(00:00 - 05:55 UTC)" in window


def test_render_dashboard_html_turkish_ui():
    """Verify Turkish presentation elements rendered in HTML."""
    state = get_engine_state()
    html = render_dashboard_html(state)

    # Technical brands intact
    assert "Coin Behavior Engine" in html
    assert "CBE-0.7.0" in html
    assert "SHA-256:" in html
    assert "/health" in html
    assert "/api/status" in html

    # Localized header & badges
    assert "MODEL DONDURULDU: CBE-0.7.0" in html
    assert "DENETİM: %100 BAŞARILI" in html
    assert "CANLI İZLEME" in html

    # Localized cards
    assert "DONDURULMUŞ MODEL" in html
    assert "Araştırma Bitiş Zamanı:" in html
    assert "FAZ A — İLK İLERİYE DÖNÜK GÖZLEM" in html
    assert "72 Mum" in html
    assert "TAMAMLANDI" in html
    assert "FAZ B — İLERİYE DÖNÜK CANLI GÖZLEM" in html
    assert "108 Mum" in html
    assert "AKTİF" in html
    assert "KİLİTLİ KAYIT & DENETİM BÜTÜNLÜĞÜ" in html
    assert "0 İhlal" in html

    # Localized sprint table
    assert "Sprint 01–08 Bilimsel Araştırma ve Doğrulama Süreci" in html
    assert "BİLGİ KATMANI" in html
    assert "DOĞRULANMIŞ YÖN TAHMİNİ?" in html
    assert "DOĞRULANMIŞ VOLATİLİTE / RİSK BİLGİSİ?" in html
    assert "Spot Piyasa Yapısı ve Metodoloji" in html
    assert "Tarihsel Benzerlik Analizi" in html
    assert "Doğrulandı (Volatilite / Tail Risk Bağlamı)" in html
    assert "Sınırlı (Bağlamsal / Gecikmeli Bilgi)" in html
    assert "Birleşik Olasılıksal Motor (CBE-0.7.0)" in html
    assert "Yön Tahmini Kullanılmıyor" in html
    assert "İleriye Dönük Doğrulama ve Denetim Kaydı" in html
    assert "DENETLENDİ" in html
    assert "DONDURULDU" in html
    assert "İZLENİYOR" in html

    # Localized API descriptions
    assert "Konteyner sağlık kontrolü (HTTP 200)" in html
    assert "Canlı ileriye dönük motor durumu ve model dondurma doğrulaması" in html
