"""Generate Deliverables 01-08 for Sprint 32 Scientific Validation & Closure.

Outputs to:
  1) research_outputs/sprint32_scientific_validation_dashboard_v10/
  2) C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97/
"""

import json
import shutil
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from coin_behavior_engine.product.btc_timing_research.dataset_provenance_auditor import DatasetProvenanceAuditor
from coin_behavior_engine.product.btc_timing_research.statistical_claims_auditor import StatisticalClaimsAuditor
from coin_behavior_engine.product.btc_timing_research.transaction_cost_auditor import TransactionCostAuditor
from coin_behavior_engine.product.btc_timing_research.sealed_evaluation_auditor import SealedEvaluationAuditor

def main():
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "research_outputs" / "sprint32_scientific_validation_dashboard_v10"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    artifact_dir = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
    
    print("[1/4] Running Dataset Provenance & Raw-to-Merged Parity Audit...")
    prov_auditor = DatasetProvenanceAuditor()
    prov_res = prov_auditor.run_full_provenance_audit()
    prov_md = prov_auditor.generate_provenance_audit_markdown(prov_res)
    parity_md = prov_auditor.generate_raw_to_merged_markdown(prov_res)
    
    (out_dir / "01_dataset_provenance_audit.md").write_text(prov_md, encoding="utf-8")
    (out_dir / "02_raw_to_merged_data_verification.md").write_text(parity_md, encoding="utf-8")
    
    print("[2/4] Running Statistical Claims & H1-H5 Audit...")
    stat_auditor = StatisticalClaimsAuditor()
    stat_res = stat_auditor.audit_all_hypotheses()
    stat_md = stat_auditor.generate_audit_markdown(stat_res)
    stat_json = json.dumps(stat_auditor.generate_corrected_classifications_json(stat_res), indent=2)
    
    (out_dir / "03_statistical_claims_audit.md").write_text(stat_md, encoding="utf-8")
    (out_dir / "04_corrected_h1_h5_classifications.json").write_text(stat_json, encoding="utf-8")
    
    print("[3/4] Running Transaction Cost & Double-Entry Accounting Audit...")
    cost_auditor = TransactionCostAuditor()
    cost_res = cost_auditor.run_full_reconciliation()
    cost_md = cost_auditor.generate_convention_audit_markdown(cost_res)
    cost_json = json.dumps(cost_auditor.generate_reconciliation_json(cost_res), indent=2)
    
    (out_dir / "05_transaction_cost_convention_audit.md").write_text(cost_md, encoding="utf-8")
    (out_dir / "06_independent_portfolio_reconciliation.json").write_text(cost_json, encoding="utf-8")
    
    print("[4/4] Running Sealed Evaluation Chronology & Evidence Classification Audit...")
    sealed_auditor = SealedEvaluationAuditor()
    sealed_res = sealed_auditor.audit_chronology()
    sealed_md = sealed_auditor.generate_chronology_audit_markdown(sealed_res)
    sealed_json = json.dumps(sealed_auditor.generate_evidence_classification_json(sealed_res), indent=2)
    
    (out_dir / "07_policy_freeze_chronology_audit.md").write_text(sealed_md, encoding="utf-8")
    (out_dir / "08_scientific_evidence_classification.json").write_text(sealed_json, encoding="utf-8")
    
    # Also sync 01-08 to artifact dir
    if artifact_dir.exists():
        for fname in [
            "01_dataset_provenance_audit.md",
            "02_raw_to_merged_data_verification.md",
            "03_statistical_claims_audit.md",
            "04_corrected_h1_h5_classifications.json",
            "05_transaction_cost_convention_audit.md",
            "06_independent_portfolio_reconciliation.json",
            "07_policy_freeze_chronology_audit.md",
            "08_scientific_evidence_classification.json",
        ]:
            shutil.copy2(out_dir / fname, artifact_dir / fname)
            print(f"Copied {fname} to artifacts.")

    print("Successfully generated Deliverables 01-08!")

if __name__ == "__main__":
    main()
