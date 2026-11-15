"""Run historical dataset registry reconciliation and output 10_dataset_registry_reconciliation.json."""

import json
from pathlib import Path
from coin_behavior_engine.product.dataset_registry import HistoricalDatasetRegistry

def main():
    registry = HistoricalDatasetRegistry()
    reconciliation = registry.generate_full_reconciliation(start_year=2022, end_year=2026, end_month=11)

    out_file = Path("research_outputs/sprint34_1_scientific_data_deployment_closure/10_dataset_registry_reconciliation.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(reconciliation, f, indent=2)

    print(f"Saved dataset registry reconciliation to {out_file}")
    print("Summary:", json.dumps(reconciliation["summary"], indent=2))

if __name__ == "__main__":
    main()
