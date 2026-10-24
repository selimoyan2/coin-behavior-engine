"""
CBE — Reproducible Historical Research Report Generator
Generates verifiable, mathematically bounded historical research reports
in JSON and CSV formats with exact dataset provenance, model versioning,
formula-injection protection, and mandatory Turkish regulatory disclaimers.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cbe.research_reports")

REPO_ROOT = Path(__file__).resolve().parents[3]
MANDATORY_DISCLAIMER_TR = "Bu rapor tarihsel veri araştırması amacıyla hazırlanmıştır. Yatırım tavsiyesi veya canlı alım-satım sinyali değildir."


def sanitize_csv_value(val: Any) -> Any:
    """Prepend a single quote if string starts with dangerous spreadsheet formula triggers."""
    if isinstance(val, str):
        if val.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + val
    return val


class ResearchReportGenerator:
    """Generates standardized, reproducible historical research reports."""

    @classmethod
    def get_dataset_provenance(cls) -> Dict[str, Any]:
        """Obtain current dataset manifest and hash."""
        from coin_behavior_engine.product.dataset_manager import DatasetManager
        dm = DatasetManager.get_instance()
        manifest = dm.get_manifest()
        return {
            "manifest_version": manifest.get("manifest_version", "UNKNOWN"),
            "manifest_hash": manifest.get("manifest_hash", "UNKNOWN"),
            "dataset_id": manifest.get("dataset_id", "BTCUSDT_BINANCE_SPOT_MULTIYEAR"),
            "available_months_count": len(manifest.get("available_months", [])),
            "earliest_month": manifest.get("earliest_month"),
            "latest_month": manifest.get("latest_month"),
        }

    @classmethod
    def generate_period_comparison_report(
        cls,
        month_a: str,
        month_b: str,
        interval: str = "1h",
        export_format: str = "json",
    ) -> Dict[str, Any]:
        """Generate research report comparing two historical months."""
        from coin_behavior_engine.product.comparative_workbench import ComparativeMarketEngine
        
        comp_res = ComparativeMarketEngine.compare_periods(
            period_a={"month": month_a, "interval": interval},
            period_b={"month": month_b, "interval": interval},
            anchor_a=0,
            anchor_b=0,
        )

        provenance = cls.get_dataset_provenance()
        report_id = f"RPT-PER-COMP-{hashlib.sha256(f'{month_a}_{month_b}_{interval}_{datetime.now(timezone.utc).isoformat()}'.encode()).hexdigest()[:12]}"

        report_data = {
            "report_id": report_id,
            "report_type": "HISTORICAL_PERIOD_COMPARISON",
            "title": f"Tarihsel Dönem Karşılaştırma Raporu ({month_a} vs {month_b})",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": "CBE-0.7.0",
            "disclaimer_tr": MANDATORY_DISCLAIMER_TR,
            "dataset_provenance": provenance,
            "parameters": {
                "period_a_month": month_a,
                "period_b_month": month_b,
                "interval": interval,
            },
            "comparison_metrics": comp_res.get("comparison", {}),
            "delta_metrics": comp_res.get("delta_metrics", {}),
        }

        if export_format.lower() == "csv":
            csv_str = cls._convert_metrics_to_csv(report_data)
            report_data["csv_content"] = csv_str

        return report_data

    @classmethod
    def generate_macro_event_report(
        cls,
        event_id_a: str,
        event_id_b: Optional[str] = None,
        interval: str = "1h",
        window_hours: int = 24,
        export_format: str = "json",
    ) -> Dict[str, Any]:
        """Generate research report for macro event impacts."""
        from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine

        ev_a = MacroEventComparisonEngine.get_event_by_id(event_id_a)
        if not ev_a:
            return {
                "status": "NOT_FOUND",
                "error": f"Olay '{event_id_a}' arşivde bulunamadı.",
                "disclaimer_tr": MANDATORY_DISCLAIMER_TR,
            }

        provenance = cls.get_dataset_provenance()
        report_id = f"RPT-MACRO-{hashlib.sha256(f'{event_id_a}_{event_id_b}_{interval}'.encode()).hexdigest()[:12]}"

        if event_id_b:
            comp_res = MacroEventComparisonEngine.compare_two_events(
                event_id_a=event_id_a,
                event_id_b=event_id_b,
                interval=interval,
                window_hours=window_hours,
            )
            title = f"Makro Olay Karşılaştırma Raporu ({event_id_a} vs {event_id_b})"
            content = comp_res
        else:
            impact_res = MacroEventComparisonEngine.analyze_event_impact(
                event=ev_a,
                interval=interval,
                pre_hours=window_hours,
                post_hours=window_hours,
            )
            title = f"Makro Olay Etki Analizi Raporu ({event_id_a} - {ev_a.event_name})"
            content = impact_res

        report_data = {
            "report_id": report_id,
            "report_type": "MACRO_EVENT_SYNCHRONIZED_STUDY",
            "title": title,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": "CBE-0.7.0",
            "disclaimer_tr": MANDATORY_DISCLAIMER_TR,
            "dataset_provenance": provenance,
            "parameters": {
                "event_id_a": event_id_a,
                "event_id_b": event_id_b,
                "interval": interval,
                "window_hours": window_hours,
            },
            "results": content,
        }

        if export_format.lower() == "csv":
            csv_str = cls._convert_macro_to_csv(report_data)
            report_data["csv_content"] = csv_str

        return report_data

    @classmethod
    def generate_regime_drift_report(
        cls,
        baseline_month: str = "2026-08",
        target_month: str = "2026-09",
        interval: str = "1h",
        export_format: str = "json",
    ) -> Dict[str, Any]:
        """Generate research report on regime distribution drift and stability."""
        from coin_behavior_engine.product.regime_drift import RegimeDriftEngine

        drift_res = RegimeDriftEngine.analyze_drift_for_months(
            baseline_month=baseline_month,
            target_month=target_month,
        )

        provenance = cls.get_dataset_provenance()
        report_id = f"RPT-DRIFT-{hashlib.sha256(f'{baseline_month}_{target_month}_{interval}'.encode()).hexdigest()[:12]}"

        report_data = {
            "report_id": report_id,
            "report_type": "REGIME_DRIFT_INTELLIGENCE",
            "title": f"Rejim Dağılım Kayması & Kararlılık Raporu ({baseline_month} -> {target_month})",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": "CBE-0.7.0",
            "disclaimer_tr": MANDATORY_DISCLAIMER_TR,
            "dataset_provenance": provenance,
            "parameters": {
                "baseline_month": baseline_month,
                "target_month": target_month,
                "interval": interval,
            },
            "drift_telemetry": drift_res,
        }

        if export_format.lower() == "csv":
            csv_str = cls._convert_drift_to_csv(report_data)
            report_data["csv_content"] = csv_str

        return report_data

    @classmethod
    def _convert_metrics_to_csv(cls, report: Dict[str, Any]) -> str:
        """Convert period comparison metrics to safe CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["# CBE REPRODUCIBLE RESEARCH REPORT"])
        writer.writerow(["# Report ID", sanitize_csv_value(report["report_id"])])
        writer.writerow(["# Generated UTC", sanitize_csv_value(report["generated_at_utc"])])
        writer.writerow(["# Model Version", sanitize_csv_value(report["model_version"])])
        writer.writerow(["# Manifest Hash", sanitize_csv_value(report["dataset_provenance"]["manifest_hash"])])
        writer.writerow(["# Disclaimer", sanitize_csv_value(report["disclaimer_tr"])])
        writer.writerow([])
        writer.writerow(["Metric", "Period A", "Period B", "Delta"])

        deltas = report.get("delta_metrics", {})
        comp = report.get("comparison", {})
        mA = comp.get("period_a", {}).get("metrics", {})
        mB = comp.get("period_b", {}).get("metrics", {})

        for k in ["net_return_pct", "amplitude_pct", "max_drawdown_pct", "realized_volatility_annualized_pct", "total_volume", "candle_count"]:
            vA = sanitize_csv_value(mA.get(k, ""))
            vB = sanitize_csv_value(mB.get(k, ""))
            vDelta = sanitize_csv_value(deltas.get(f"{k}_delta", ""))
            writer.writerow([k, vA, vB, vDelta])

        return output.getvalue()

    @classmethod
    def _convert_macro_to_csv(cls, report: Dict[str, Any]) -> str:
        """Convert macro event impact report to safe CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["# CBE REPRODUCIBLE RESEARCH REPORT - MACRO EVENT"])
        writer.writerow(["# Report ID", sanitize_csv_value(report["report_id"])])
        writer.writerow(["# Generated UTC", sanitize_csv_value(report["generated_at_utc"])])
        writer.writerow(["# Disclaimer", sanitize_csv_value(report["disclaimer_tr"])])
        writer.writerow([])

        results = report.get("results", {})
        if "delta_metrics" in results:
            writer.writerow(["Metric", "Event A", "Event B", "Delta"])
            mA = results.get("event_a", {}).get("metrics", {})
            mB = results.get("event_b", {}).get("metrics", {})
            deltas = results.get("delta_metrics", {})
            for k, val in mA.items():
                writer.writerow([k, sanitize_csv_value(val), sanitize_csv_value(mB.get(k, "")), sanitize_csv_value(deltas.get(f"{k}_delta", deltas.get(f"{k}_delta_pct", "")))])
        elif "metrics" in results:
            writer.writerow(["Metric", "Value"])
            for k, v in results.get("metrics", {}).items():
                writer.writerow([k, sanitize_csv_value(v)])

        return output.getvalue()

    @classmethod
    def _convert_drift_to_csv(cls, report: Dict[str, Any]) -> str:
        """Convert regime drift report to safe CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["# CBE REPRODUCIBLE RESEARCH REPORT - REGIME DRIFT"])
        writer.writerow(["# Report ID", sanitize_csv_value(report["report_id"])])
        writer.writerow(["# Disclaimer", sanitize_csv_value(report["disclaimer_tr"])])
        writer.writerow([])
        writer.writerow(["Metric", "Value"])
        dt = report.get("drift_telemetry", {})
        writer.writerow(["PSI Value", sanitize_csv_value(dt.get("psi_value", ""))])
        writer.writerow(["JSD Metric", sanitize_csv_value(dt.get("jensen_shannon_divergence", ""))])
        writer.writerow(["Drift Level", sanitize_csv_value(dt.get("drift_level", ""))])
        writer.writerow(["Sample Count Baseline", sanitize_csv_value(dt.get("baseline_sample_count", ""))])
        writer.writerow(["Sample Count Target", sanitize_csv_value(dt.get("target_sample_count", ""))])
        return output.getvalue()
