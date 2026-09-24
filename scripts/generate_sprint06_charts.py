"""CLI script to generate all Sprint 06 publication-quality charts."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from coin_behavior_engine.news.visualizations import generate_all_sprint06_charts

if __name__ == "__main__":
    generate_all_sprint06_charts()
    print("Sprint 06 charts generated successfully in data/reports/sprint06/charts/")
