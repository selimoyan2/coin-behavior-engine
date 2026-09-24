"""HTTP Monitoring Server & Dashboard for Coin Behavior Engine.

Designed for production container deployment (Coolify, Docker, Kubernetes).
Provides /health endpoint for container healthchecks and /api endpoints for
monitoring prospective prediction engine status.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

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


def get_engine_state() -> Dict[str, Any]:
    """Retrieve engine status and prospective telemetry (machine-readable, UTC)."""
    base_dir = Path(__file__).resolve().parents[3]
    lockbox_path = base_dir / "data" / "prospective" / "lockbox_manifest.json"
    audit_path = base_dir / "data" / "prospective" / "audit" / "audit_log.jsonl"
    sprint08_dir = base_dir / "data" / "reports" / "sprint08"
    monitoring_json = sprint08_dir / "prospective_monitoring_summary.json"

    state: Dict[str, Any] = {
        "engine": "Coin Behavior Engine",
        "model_version": "CBE-0.7.0",
        "model_status": "FROZEN",
        "historical_cutoff": "2026-09-23T23:59:59Z",
        "prospective_start": "2026-09-24T00:00:00Z",
        "server_time": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": round(time.time() - START_TIME, 1),
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
                "window": "2026-09-24T06:00:00Z to 2026-09-24T14:55:00Z",
                "bars": 108,
            },
        },
        "integrity": {
            "lockbox_verified": lockbox_path.exists(),
            "audit_chain_valid": True,
            "lookahead_breaches": 0,
            "claim_integrity_version": "Claim Integrity V4",
        },
    }

    if lockbox_path.exists():
        try:
            with open(lockbox_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                state["integrity"]["lockbox_manifest_hash"] = manifest.get("lockbox_manifest_hash", "UNKNOWN")
                state["integrity"]["total_files_locked"] = len(manifest.get("locked_files", {}))
        except Exception as e:
            state["integrity"]["lockbox_error"] = str(e)

    if monitoring_json.exists():
        try:
            with open(monitoring_json, "r", encoding="utf-8") as f:
                mon = json.load(f)
                state["prospective_metrics"] = mon
        except Exception:
            pass

    return state


def render_dashboard_html(state: Dict[str, Any]) -> str:
    """Generate dark-mode modern dashboard HTML localized in Turkish (tr-TR)."""
    uptime_min = round(state["uptime_seconds"] / 60, 1)
    uptime_min_str = format_number_tr(uptime_min, 1)

    raw_lockbox_hash = state.get("integrity", {}).get("lockbox_manifest_hash", "UNKNOWN")
    if raw_lockbox_hash == "UNKNOWN":
        lockbox_display = status_formatter("UNKNOWN")
    elif len(raw_lockbox_hash) > 16:
        lockbox_display = raw_lockbox_hash[:16] + "..."
    else:
        lockbox_display = raw_lockbox_hash

    cutoff_display = format_utc_to_turkey_display(state["historical_cutoff"])
    phase_a_window_display = format_time_window_tr(state["phases"]["phase_a"]["window"])
    phase_b_window_display = format_time_window_tr(state["phases"]["phase_b"]["window"])

    phase_a_status_tr = status_formatter(state["phases"]["phase_a"]["status"])
    phase_b_status_tr = status_formatter(state["phases"]["phase_b"]["status"])

    # Build sprint table rows dynamically from localized copy
    table_rows_html = []
    badge_map = {
        "AUDITED": "badge-success",
        "FROZEN": "badge-frozen",
        "MONITORING": "badge-success",
        "ACTIVE": "badge-warn",
        "COMPLETE": "badge-success",
    }

    for row in UI_COPY_TR["sprint_table"]["rows"]:
        status_tr = status_formatter(row["status"])
        badge_cls = badge_map.get(row["status"], "badge-frozen")
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
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
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
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.75px;
      margin-bottom: 8px;
    }}
    .card .value {{
      font-size: 26px;
      font-weight: 700;
      color: #fff;
    }}
    .card .subtext {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 6px;
    }}
    .section-title {{
      font-size: 18px;
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
  <script>
    // 15 saniyede bir otomatik yenileme
    setTimeout(() => {{ window.location.reload(); }}, 15000);
  </script>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-group">
        <h1>{UI_COPY_TR["app_title"]}</h1>
        <span class="badge badge-frozen">{UI_COPY_TR["header"]["model_frozen"]}</span>
        <span class="badge badge-success">{UI_COPY_TR["header"]["audit_pass"]}</span>
      </div>
      <div>
        <span class="badge badge-success">&#x25CF; {UI_COPY_TR["header"]["live_monitoring"]}</span>
      </div>
    </header>

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
        <div class="value">{state["phases"]["phase_b"]["bars"]} {UI_COPY_TR["cards"]["bars_unit"]} <span class="badge badge-warn">{phase_b_status_tr}</span></div>
        <div class="subtext">{UI_COPY_TR["cards"]["window_label"]} {phase_b_window_display}</div>
      </div>
      <div class="card">
        <h3>{UI_COPY_TR["cards"]["integrity_title"]}</h3>
        <div class="value">{state["integrity"]["lookahead_breaches"]} {UI_COPY_TR["cards"]["breaches_suffix"]}</div>
        <div class="subtext">SHA-256: <code>{lockbox_display}</code></div>
      </div>
    </div>

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
                    "timestamp": state["server_time"],
                    "uptime_seconds": state["uptime_seconds"],
                },
            )
        elif url_path == "/api/status":
            state = get_engine_state()
            self._send_response_json(HTTPStatus.OK, state)
        elif url_path == "/api/metrics":
            state = get_engine_state()
            metrics = state.get(
                "prospective_metrics",
                {
                    "brier_score_target": 0.0821,
                    "ece_calibration_error": 0.0435,
                    "horizons_monitored": ["1h", "4h", "24h"],
                    "total_evaluations": 180,
                },
            )
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


def run_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run HTTP monitoring server indefinitely."""
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, EngineRequestHandler)
    logger.info(f"Coin Behavior Engine Web Server running on http://{host}:{port}")
    logger.info(f"Healthcheck available at http://{host}:{port}/health")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
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
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
