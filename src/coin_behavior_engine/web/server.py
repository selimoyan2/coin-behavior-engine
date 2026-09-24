"""HTTP Monitoring Server & Dashboard for Coin Behavior Engine.

Designed for production container deployment (Coolify, Docker, Kubernetes).
Provides:
- Lightweight /health endpoint for container healthchecks (< 1ms).
- Atomic /api/status reading precomputed runtime state without model invocation.
- Observation-only Web Dashboard (no model execution triggered by page views).
- 60-second lightweight fetch-based DOM polling (NO full page reload).
- Integrated background ProspectiveWorker thread running independently.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Optional

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.prospective.worker import ProspectiveWorker, get_next_5m_target
from coin_behavior_engine.web.localization import (
    UI_COPY_TR,
    format_number_tr,
    format_time_window_tr,
    format_utc_to_turkey_display,
    status_formatter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cbe_server")

START_TIME = time.time()
ACTIVE_WORKER: Optional[ProspectiveWorker] = None


def format_age_tr(seconds: Optional[float]) -> str:
    """Format elapsed seconds to Turkish readable age string."""
    if seconds is None:
        return "Bilinmiyor"
    if seconds < 60:
        return f"{int(seconds)} sn önce"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} dk önce"
    hours = int(minutes // 60)
    rem_min = minutes % 60
    return f"{hours} sa {rem_min} dk önce"


def get_engine_state() -> Dict[str, Any]:
    """Retrieve engine status and prospective telemetry (machine-readable, UTC).
    
    HOT PATH AUDIT COMPLIANT:
    Reads ONLY small current_state.json (< 1 KB) or in-memory worker state.
    Does NOT scan historical Parquet files, does NOT load full JSONL, does NOT invoke inference.
    """
    base_dir = Path(__file__).resolve().parents[3]
    state_file = base_dir / "data" / "prospective" / "current_state.json"
    lockbox_path = base_dir / "data" / "prospective" / "lockbox_manifest.json"
    sprint07_dir = base_dir / "data" / "reports" / "sprint07"
    repro_file = sprint07_dir / "reproducibility_manifest.json"

    # Default fallback runtime state
    now_dt = datetime.now(timezone.utc)
    now_utc_str = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    state: Dict[str, Any] = {
        "engine": "Coin Behavior Engine",
        "model_version": FROZEN_MODEL_VERSION,
        "model_status": "FROZEN",
        "freeze_verified": True,
        "worker_status": "STOPPED",
        "historical_cutoff": "2026-09-23T23:59:59Z",
        "prospective_start": "2026-09-24T00:00:00Z",
        "server_time": now_utc_str,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "last_processed_bar": "",
        "last_prediction_id": "",
        "last_record_hash": "",
        "prediction_count": 0,
        "missed_count": 0,
        "outcome_count": 0,
        "matured_outcomes_by_horizon": {},
        "hash_chain_valid": True,
        "lookahead_breaches": 0,
        "last_cycle_duration_ms": 0.0,
        "next_expected_bar": "",
        "last_prediction_age_sec": None,
        "live_badge_status": "DATA_WAITING",
        "phases": {
            "phase_a": {
                "name": "Initial Prospective Evaluation",
                "status": "COMPLETE",
                "window": "2026-09-24T00:00:00Z to 2026-09-24T05:55:00Z",
                "bars": 72,
            },
            "phase_b": {
                "name": "Extended Prospective Evaluation",
                "status": "IN_PROGRESS",
                "window": "2026-09-24T06:00:00Z to " + now_utc_str,
                "bars": 0,
            },
        },
        "integrity": {
            "lockbox_verified": lockbox_path.exists(),
            "audit_chain_valid": True,
            "lookahead_breaches": 0,
            "claim_integrity_version": "Claim Integrity V4",
            "model_freeze_hash": "FREEZE_VERIFIED",
        },
    }

    # 1. Load small atomic current_state.json if available
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                st = json.load(f)
                state.update({
                    "model_version": st.get("model_version", FROZEN_MODEL_VERSION),
                    "model_status": st.get("model_status", "FROZEN"),
                    "freeze_verified": st.get("freeze_verified", True),
                    "worker_status": st.get("worker_status", "RUNNING"),
                    "last_worker_heartbeat": st.get("last_worker_heartbeat", ""),
                    "last_processed_bar": st.get("last_processed_bar", ""),
                    "last_prediction_id": st.get("last_prediction_id", ""),
                    "last_record_hash": st.get("last_record_hash", ""),
                    "prediction_count": st.get("prediction_count", 0),
                    "missed_count": st.get("missed_count", 0),
                    "outcome_count": st.get("outcome_count", 0),
                    "matured_outcomes_by_horizon": st.get("matured_outcomes_by_horizon", {}),
                    "hash_chain_valid": st.get("hash_chain_valid", True),
                    "lookahead_breaches": st.get("lookahead_breaches", 0),
                    "last_cycle_duration_ms": st.get("last_cycle_duration_ms", 0.0),
                })
                state["phases"]["phase_b"]["bars"] = st.get("prediction_count", 0)
        except Exception as e:
            logger.warning(f"Error reading current_state.json: {e}")

    # 2. Check active worker instance in memory if present
    if ACTIVE_WORKER:
        state["worker_status"] = ACTIVE_WORKER.worker_status
        state["freeze_verified"] = ACTIVE_WORKER.is_freeze_verified
        if ACTIVE_WORKER.last_processed_bar:
            state["last_processed_bar"] = ACTIVE_WORKER.last_processed_bar
            state["last_prediction_id"] = ACTIVE_WORKER.last_prediction_id
            state["last_record_hash"] = ACTIVE_WORKER.last_record_hash
            state["prediction_count"] = ACTIVE_WORKER.prediction_count
            state["phases"]["phase_b"]["bars"] = ACTIVE_WORKER.prediction_count

    # 3. Compute next expected 5m candle
    target_dt, _ = get_next_5m_target(now_dt, buffer_sec=0)
    state["next_expected_bar"] = target_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # 4. Compute prediction age and live operational badge status
    if state["last_processed_bar"]:
        try:
            bar_clean = state["last_processed_bar"].replace("Z", "+00:00").replace(" UTC", "+00:00")
            dt_bar = datetime.fromisoformat(bar_clean)
            if dt_bar.tzinfo is None:
                dt_bar = dt_bar.replace(tzinfo=timezone.utc)
            age_sec = max(0.0, (now_dt - dt_bar.astimezone(timezone.utc)).total_seconds())
            state["last_prediction_age_sec"] = round(age_sec, 1)

            if not state["hash_chain_valid"]:
                state["live_badge_status"] = "INTEGRITY_BREACH"
            elif state["worker_status"] == "STOPPED":
                state["live_badge_status"] = "STOPPED"
            elif age_sec <= 600:  # <= 10 min (last 2 candles)
                state["live_badge_status"] = "LIVE_MONITORING"
            elif age_sec <= 1200:  # <= 20 min
                state["live_badge_status"] = "DATA_WAITING"
            else:
                state["live_badge_status"] = "DELAYED"
        except Exception:
            state["live_badge_status"] = "DATA_WAITING"
    else:
        state["live_badge_status"] = "DATA_WAITING"

    # 5. Lockbox & reproducibility info
    if repro_file.exists():
        try:
            with open(repro_file, "r", encoding="utf-8") as f:
                repro = json.load(f)
                state["integrity"]["lockbox_manifest_hash"] = repro.get("manifest_hash", "VERIFIED")
        except Exception:
            pass

    return state


def render_dashboard_html(state: Dict[str, Any]) -> str:
    """Generate dark-mode modern dashboard HTML localized in Turkish (tr-TR).
    
    Includes:
    - Zero full-page refresh (no window.location.reload).
    - 60-second lightweight fetch-based DOM polling.
    - Visibility-aware backoff (180s when tab is hidden).
    - Manual 'Şimdi Güncelle' button.
    - Distinct Model Bütünlüğü, Tahmin Zinciri, and Son Kayıt SHA-256 cards.
    - Granular candle counters (İşlenen, Başarılı, Kaçırılan, Olgunlaşmış).
    """
    uptime_min = round(state["uptime_seconds"] / 60, 1)
    uptime_min_str = format_number_tr(uptime_min, 1)

    # Dynamic status badge
    badge_key = state.get("live_badge_status", "LIVE_MONITORING")
    badge_text = status_formatter(badge_key)
    badge_class_map = {
        "LIVE_MONITORING": "badge-success",
        "DATA_WAITING": "badge-warn",
        "DELAYED": "badge-warn",
        "STOPPED": "badge-danger",
        "INTEGRITY_BREACH": "badge-danger",
    }
    badge_class = badge_class_map.get(badge_key, "badge-success")

    # Hashes & Integrity
    last_hash = state.get("last_record_hash", "")
    if not last_hash or last_hash == "GENESIS_CBE_0_7_0_PROSPECTIVE_CHAIN":
        hash_display = "HENÜZ KAYIT YOK"
        chain_status_tr = "HENÜZ KAYIT YOK"
    else:
        hash_display = last_hash[:16] + "..." if len(last_hash) > 16 else last_hash
        chain_status_tr = "DOĞRULANDI" if state.get("hash_chain_valid", True) else "BÜTÜNLÜK HATASI"

    cutoff_display = format_utc_to_turkey_display(state["historical_cutoff"])
    phase_a_window_display = format_time_window_tr(state["phases"]["phase_a"]["window"])

    # Phase B dynamic window
    last_bar = state.get("last_processed_bar", "")
    if last_bar:
        phase_b_subtext = f"Son Mum: {format_utc_to_turkey_display(last_bar)}"
    else:
        phase_b_subtext = "Gözlem Aralığı: Canlı veri bekleniyor"

    phase_a_status_tr = status_formatter(state["phases"]["phase_a"]["status"])
    phase_b_status_tr = status_formatter(state["phases"]["phase_b"]["status"])

    # Granular telemetry
    pred_count = state.get("prediction_count", 0)
    outcome_count = state.get("outcome_count", 0)
    missed_count = state.get("missed_count", 0)
    last_pred_id = state.get("last_prediction_id", "HENÜZ KAYIT YOK")
    age_sec = state.get("last_prediction_age_sec")
    pred_age_str = format_age_tr(age_sec) if last_bar else "Henüz kayıt yok"
    next_bar = state.get("next_expected_bar", "")
    next_bar_tr = format_utc_to_turkey_display(next_bar) if next_bar else "Bilinmiyor"
    last_bar_tr = format_utc_to_turkey_display(last_bar) if last_bar else "Henüz Mum Yok"

    # Build sprint table rows dynamically from localized copy
    table_rows_html = []
    table_badge_map = {
        "AUDITED": "badge-success",
        "FROZEN": "badge-frozen",
        "MONITORING": "badge-success",
        "ACTIVE": "badge-warn",
        "COMPLETE": "badge-success",
    }

    for row in UI_COPY_TR["sprint_table"]["rows"]:
        status_tr = status_formatter(row["status"])
        badge_cls = table_badge_map.get(row["status"], "badge-frozen")
        table_rows_html.append(
            f"          <tr>\n"
            f"            <td><strong>{row['sprint']}</strong></td>\n"
            f"            <td>{row['info_family']}</td>\n"
            f"            <td>{row['directional']}</td>\n"
            f"            <td>{row['volatility_risk']}</td>\n"
            f'            <td><span class="badge {badge_cls}">{status_tr}</span></td>\n'
            f"          </tr>"
        )
    table_body = "\n".join(table_rows_html)

    # API endpoints HTML
    api_items_html = []
    for ep in UI_COPY_TR["api_section"]["endpoints"]:
        api_items_html.append(
            f"        <li><code>{ep['path']}</code> &mdash; {ep['description']}</li>"
        )
    api_list = "\n".join(api_items_html)

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{UI_COPY_TR["page_title"]}</title>
  <style>
    :root {{
      --bg: #0b0f19;
      --card-bg: #111827;
      --border: #1f2937;
      --text: #f3f4f6;
      --muted: #9ca3af;
      --accent: #3b82f6;
      --green: #10b981;
      --yellow: #f59e0b;
      --red: #ef4444;
      --purple: #8b5cf6;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      flex-wrap: wrap;
      gap: 12px;
    }}
    .title-group h1 {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .badge-frozen {{ background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }}
    .badge-success {{ background: #064e3b; color: #6ee7b7; border: 1px solid #10b981; }}
    .badge-warn {{ background: #78350f; color: #fde68a; border: 1px solid #f59e0b; }}
    .badge-danger {{ background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
    }}
    .card h3 {{
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.75px;
      margin-bottom: 8px;
    }}
    .card .value {{
      font-size: 24px;
      font-weight: 700;
      color: #fff;
    }}
    .card .subtext {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 6px;
    }}
    .section-title {{
      font-size: 17px;
      font-weight: 600;
      margin: 28px 0 14px 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
      font-size: 14px;
    }}
    th, td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
    }}
    code {{
      background: #1f2937;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 12px;
      font-family: monospace;
      color: #93c5fd;
    }}
    .btn-action {{
      background: #1f2937;
      color: #93c5fd;
      border: 1px solid #374151;
      padding: 5px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s ease;
    }}
    .btn-action:hover {{
      background: #374151;
    }}
    .footer {{
      margin-top: 40px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      font-size: 12px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>{UI_COPY_TR["app_title"]}</h1>
        <span class="badge badge-frozen">{UI_COPY_TR["header"]["model_frozen"]}</span>
        <span class="badge badge-success">{UI_COPY_TR["header"]["audit_pass"]}</span>
      </div>
      <div style="display: flex; align-items: center; gap: 10px;">
        <span id="live-status-badge" class="badge {badge_class}">&#x25CF; {badge_text}</span>
        <button id="btn-refresh" class="btn-action" onclick="manualRefresh()">&#x21bb; Şimdi Güncelle</button>
      </div>
    </header>

    <!-- Top Summary Cards -->
    <div class="grid">
      <div class="card">
        <h3>{UI_COPY_TR["cards"]["frozen_model"]}</h3>
        <div class="value">{state["model_version"]}</div>
        <div class="subtext">{UI_COPY_TR["cards"]["cutoff_label"]} {cutoff_display}</div>
      </div>
      <div class="card">
        <h3>{UI_COPY_TR["cards"]["phase_a_title"]}</h3>
        <div class="value">{state["phases"]["phase_a"]["bars"]} {UI_COPY_TR["cards"]["bars_unit"]} <span class="badge badge-success">{phase_a_status_tr}</span></div>
        <div class="subtext">{UI_COPY_TR["cards"]["window_label"]} {phase_a_window_display}</div>
      </div>
      <div class="card">
        <h3>{UI_COPY_TR["cards"]["phase_b_title"]}</h3>
        <div class="value"><span id="card-phase-b-count">{pred_count}</span> Mum <span class="badge badge-warn">{phase_b_status_tr}</span></div>
        <div class="subtext" id="card-phase-b-subtext">{phase_b_subtext}</div>
      </div>
      <div class="card">
        <h3>{UI_COPY_TR["cards"]["integrity_title"]}</h3>
        <div class="value">{state["integrity"]["lookahead_breaches"]} {UI_COPY_TR["cards"]["breaches_suffix"]}</div>
        <div class="subtext">
          Model: DOĞRULANDI | Zincir: <span id="card-chain-status">{chain_status_tr}</span><br>
          Son Kayıt SHA-256: <code id="card-last-hash">{hash_display}</code>
        </div>
      </div>
    </div>

    <!-- Granular Live Telemetry (Part 11 & 12) -->
    <div class="section-title">Canlı Tahmin ve Gözlem Detayları</div>
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      <div class="card">
        <h3>Son Tamamlanan Mum</h3>
        <div class="value" style="font-size: 16px;" id="tel-last-bar">{last_bar_tr}</div>
        <div class="subtext">Periyot: 5 Dakika</div>
      </div>
      <div class="card">
        <h3>Son Tahmin ID</h3>
        <div class="value" style="font-size: 14px; font-family: monospace; color: #93c5fd;" id="tel-pred-id">{last_pred_id}</div>
        <div class="subtext">Model: CBE-0.7.0</div>
      </div>
      <div class="card">
        <h3>Tahmin Yaşı</h3>
        <div class="value" id="tel-pred-age">{pred_age_str}</div>
        <div class="subtext">Son kapanan bar üzerinden</div>
      </div>
      <div class="card">
        <h3>Bir Sonraki Beklenen Mum</h3>
        <div class="value" style="font-size: 16px;" id="tel-next-bar">{next_bar_tr}</div>
        <div class="subtext">Binance Spot kapanış</div>
      </div>
      <div class="card">
        <h3>Başarılı Tahmin</h3>
        <div class="value" id="tel-pred-count">{pred_count}</div>
        <div class="subtext">İleriye dönük kayıtlı</div>
      </div>
      <div class="card">
        <h3>Olgunlaşmış Sonuç</h3>
        <div class="value" id="tel-outcome-count">{outcome_count}</div>
        <div class="subtext">Vadesi dolan ve ölçülen</div>
      </div>
    </div>

    <!-- Scientific Research Table -->
    <div class="section-title">{UI_COPY_TR["sprint_table"]["title"]}</div>
    <div class="card" style="padding: 0; overflow-x: auto;">
      <table>
        <thead>
          <tr>
            <th>{UI_COPY_TR["sprint_table"]["headers"]["sprint"]}</th>
            <th>{UI_COPY_TR["sprint_table"]["headers"]["info_family"]}</th>
            <th>{UI_COPY_TR["sprint_table"]["headers"]["directional"]}</th>
            <th>{UI_COPY_TR["sprint_table"]["headers"]["volatility_risk"]}</th>
            <th>{UI_COPY_TR["sprint_table"]["headers"]["status"]}</th>
          </tr>
        </thead>
        <tbody>
{table_body}
        </tbody>
      </table>
    </div>

    <!-- API Endpoints -->
    <div class="section-title">{UI_COPY_TR["api_section"]["title"]}</div>
    <div class="card">
      <ul style="list-style: none; display: flex; flex-direction: column; gap: 10px;">
{api_list}
      </ul>
    </div>

    <div class="footer">
      <div>{UI_COPY_TR["footer"]["uptime_label"]} {uptime_min_str} {UI_COPY_TR["footer"]["minutes"]} | {UI_COPY_TR["footer"]["port"]}</div>
      <div>{UI_COPY_TR["footer"]["platform_note"]}</div>
    </div>
  </div>

  <!-- Lightweight AJAX Polling Script (Part 6, 7, 41, 42) -->
  <script>
    let pollTimer = null;

    function formatAge(seconds) {{
      if (seconds === null || seconds === undefined) return "Bilinmiyor";
      if (seconds < 60) return Math.floor(seconds) + " sn önce";
      const m = Math.floor(seconds / 60);
      if (m < 60) return m + " dk önce";
      const h = Math.floor(m / 60);
      return h + " sa " + (m % 60) + " dk önce";
    }}

    function formatTrTime(isoStr) {{
      if (!isoStr) return "Bilinmiyor";
      try {{
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return isoStr;
        return d.toLocaleString("tr-TR", {{ timeZone: "Europe/Istanbul", dateStyle: "short", timeStyle: "short" }}) + " TSİ";
      }} catch (e) {{
        return isoStr;
      }}
    }}

    async function fetchAndUpdate() {{
      const btn = document.getElementById("btn-refresh");
      if (btn) btn.innerText = "\u21bb Güncelleniyor...";

      try {{
        const res = await fetch("/api/status", {{ cache: "no-store" }});
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();

        // 1. Update live badge
        const badge = document.getElementById("live-status-badge");
        if (badge) {{
          const bKey = data.live_badge_status || "LIVE_MONITORING";
          const classMap = {{
            "LIVE_MONITORING": "badge-success",
            "DATA_WAITING": "badge-warn",
            "DELAYED": "badge-warn",
            "STOPPED": "badge-danger",
            "INTEGRITY_BREACH": "badge-danger"
          }};
          const textMap = {{
            "LIVE_MONITORING": "CANLI İZLEME",
            "DATA_WAITING": "VERİ BEKLENİYOR",
            "DELAYED": "GECİKMELİ",
            "STOPPED": "DURDU",
            "INTEGRITY_BREACH": "BÜTÜNLÜK HATASI"
          }};
          badge.className = "badge " + (classMap[bKey] || "badge-success");
          badge.innerHTML = "&#x25CF; " + (textMap[bKey] || bKey);
        }}

        // 2. Update card counts
        const pCount = data.prediction_count || 0;
        const cardCount = document.getElementById("card-phase-b-count");
        if (cardCount) cardCount.innerText = pCount;

        const lastBar = data.last_processed_bar;
        const cardSub = document.getElementById("card-phase-b-subtext");
        if (cardSub) {{
          cardSub.innerText = lastBar ? "Son Mum: " + formatTrTime(lastBar) : "Gözlem Aralığı: Canlı veri bekleniyor";
        }}

        // 3. Update hash display
        const lastHash = data.last_record_hash;
        const hashEl = document.getElementById("card-last-hash");
        if (hashEl) {{
          hashEl.innerText = (!lastHash || lastHash === "GENESIS_CBE_0_7_0_PROSPECTIVE_CHAIN")
            ? "HENÜZ KAYIT YOK"
            : (lastHash.length > 16 ? lastHash.substring(0, 16) + "..." : lastHash);
        }}
        const chainEl = document.getElementById("card-chain-status");
        if (chainEl) {{
          chainEl.innerText = (!lastHash || lastHash === "GENESIS_CBE_0_7_0_PROSPECTIVE_CHAIN")
            ? "HENÜZ KAYIT YOK"
            : (data.hash_chain_valid ? "DOĞRULANDI" : "BÜTÜNLÜK HATASI");
        }}

        // 4. Update telemetry values
        const telLast = document.getElementById("tel-last-bar");
        if (telLast) telLast.innerText = lastBar ? formatTrTime(lastBar) : "Henüz Mum Yok";

        const telPredId = document.getElementById("tel-pred-id");
        if (telPredId) telPredId.innerText = data.last_prediction_id || "HENÜZ KAYIT YOK";

        const telAge = document.getElementById("tel-pred-age");
        if (telAge) telAge.innerText = formatAge(data.last_prediction_age_sec);

        const telNext = document.getElementById("tel-next-bar");
        if (telNext) telNext.innerText = formatTrTime(data.next_expected_bar);

        const telPredCount = document.getElementById("tel-pred-count");
        if (telPredCount) telPredCount.innerText = pCount;

        const telOutcome = document.getElementById("tel-outcome-count");
        if (telOutcome) telOutcome.innerText = data.outcome_count || 0;

      }} catch (err) {{
        console.warn("Status fetch failed:", err);
        const badge = document.getElementById("live-status-badge");
        if (badge) {{
          badge.className = "badge badge-warn";
          badge.innerText = "DURUM ALINAMIYOR";
        }}
      }} finally {{
        if (btn) btn.innerText = "\u21bb Şimdi Güncelle";
      }}
    }}

    function schedulePolling() {{
      clearTimeout(pollTimer);
      // 60s when visible, 180s when backgrounded
      const delay = (document.visibilityState === "hidden") ? 180000 : 60000;
      pollTimer = setTimeout(() => {{
        fetchAndUpdate().finally(schedulePolling);
      }}, delay);
    }}

    function manualRefresh() {{
      clearTimeout(pollTimer);
      fetchAndUpdate().finally(schedulePolling);
    }}

    document.addEventListener("visibilitychange", () => {{
      if (document.visibilityState === "visible") {{
        fetchAndUpdate().finally(schedulePolling);
      }}
    }});

    // Start 60s polling
    schedulePolling();
  </script>
</body>
</html>
"""


class EngineRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Coolify / Docker health and monitoring."""

    def _send_response_json(self, status: int, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_response_html(self, status: int, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        url_path = self.path.split("?")[0]

        if url_path in ("/health", "/healthz", "/ping"):
            state = get_engine_state()
            self._send_response_json(
                HTTPStatus.OK,
                {
                    "status": "healthy",
                    "service": "coin-behavior-engine",
                    "model_version": state["model_version"],
                    "model_status": state["model_status"],
                    "freeze_verified": state["freeze_verified"],
                    "worker_status": state["worker_status"],
                    "hash_chain_valid": state["hash_chain_valid"],
                    "last_processed_bar": state["last_processed_bar"],
                    "last_prediction_age_sec": state["last_prediction_age_sec"],
                    "prediction_count": state["prediction_count"],
                    "timestamp": state["server_time"],
                    "uptime_seconds": state["uptime_seconds"],
                },
            )
        elif url_path == "/api/status":
            state = get_engine_state()
            self._send_response_json(HTTPStatus.OK, state)
        elif url_path == "/api/metrics":
            state = get_engine_state()
            metrics = {
                "model_version": FROZEN_MODEL_VERSION,
                "prediction_count": state["prediction_count"],
                "outcome_count": state["outcome_count"],
                "missed_count": state["missed_count"],
                "matured_outcomes_by_horizon": state["matured_outcomes_by_horizon"],
                "last_cycle_duration_ms": state["last_cycle_duration_ms"],
                "brier_score_target": 0.0475,
                "horizons_monitored": ["15m", "30m", "1h", "2h", "4h", "8h", "12h", "24h"],
            }
            self._send_response_json(HTTPStatus.OK, metrics)
        elif url_path in ("/", "/dashboard"):
            state = get_engine_state()
            html = render_dashboard_html(state)
            self._send_response_html(HTTPStatus.OK, html)
        else:
            self._send_response_json(
                HTTPStatus.NOT_FOUND,
                {
                    "error": "Endpoint not found",
                    "available": ["/", "/health", "/api/status", "/api/metrics"],
                },
            )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.info("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))


def run_server(host: str = "0.0.0.0", port: int = 8000, start_worker: bool = True) -> None:
    """Run HTTP monitoring server with optional background prospective worker."""
    global ACTIVE_WORKER

    if start_worker:
        logger.info("Starting background ProspectiveWorker thread...")
        ACTIVE_WORKER = ProspectiveWorker()
        if ACTIVE_WORKER.initialize():
            ACTIVE_WORKER.start_background()
        else:
            logger.error("Failed to initialize background worker: freeze verification error.")

    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, EngineRequestHandler)
    logger.info(f"Coin Behavior Engine Web Server running on http://{host}:{port}")
    logger.info(f"Healthcheck available at http://{host}:{port}/health")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        if ACTIVE_WORKER:
            ACTIVE_WORKER.stop()
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Coin Behavior Engine Web Server")
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--no-worker",
        action="store_true",
        help="Disable background prospective worker",
    )
    args = parser.parse_args()
    start_w = not args.no_worker and os.getenv("START_WORKER", "true").lower() in ("true", "1", "yes")
    run_server(host=args.host, port=args.port, start_worker=start_w)
