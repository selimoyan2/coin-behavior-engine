"""Data quality reporting utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from coin_behavior_engine.utils.logging import logger


class DataQualityReporter:
    """Handles persistence and formatting of data quality reports."""

    def __init__(self, reports_dir: str | Path = "data/reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: Dict[str, Any], filename: str = "data_quality.json") -> Path:
        """Save report dict to JSON."""
        target_path = self.reports_dir / filename
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Saved data quality report to {target_path}")
        return target_path

    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print concise console summary of data quality findings."""
        passed = report.get("validation_passed", False)
        status = "PASSED" if passed else "FAILED / WARNINGS"
        total = report.get("total_candles", 0)
        missing = report.get("missing_candles_count", 0)
        sev = report.get("severity_summary", {})

        print("\n" + "=" * 55)
        print(f" DATA QUALITY REPORT: {status}")
        print("=" * 55)
        print(f" Total Candles:         {total:,}")
        print(f" Date Range Start:      {report.get('date_range_start_utc')}")
        print(f" Date Range End:        {report.get('date_range_end_utc')}")
        print(f" Missing Candles:       {missing}")
        print(f" Severity Breakdown:    INFO: {sev.get('INFO', 0)}, WARNING: {sev.get('WARNING', 0)}, ERROR: {sev.get('ERROR', 0)}, CRITICAL: {sev.get('CRITICAL', 0)}")
        print("=" * 55 + "\n")
