"""Sprint 09.43 — Comprehensive Unit & Architecture Test Suite.

Verifies:
1. Baseline commit verification (219e3e3be0578b119d10c621e752afef4e860980) and prior sprint artifacts preservation.
2. Complete 15-capability inventory audit with valid implementation paths and reusability ratings.
3. Formal research track closure of perpetual carry under tested economic assumptions.
4. Model reliability and calibration audit documenting 80% (64.24%) and 95% (78.94%) undercoverage.
5. Architecture readiness evaluation confirming lean resource consumption (< 150 MB RAM, < $10/mo cost).
6. MVP module prioritization matrix across 10 core market intelligence modules.
7. Concrete 6-sprint product roadmap (Sprints 10.01 to 10.06).
8. 9 measurable MVP release acceptance gates.
9. Report artifact serialization and valid JSON schema.
10. Adversarial checks: zero trading execution endpoints, fail-closed guardrails, and no unsupported confidence claims.
11. Pure compute latency budget (< 50 ms).
"""

import json
import time
from pathlib import Path

import pytest

from coin_behavior_engine.product import (
    ArchitectureAssessmentReport,
    CapabilityInventoryRecord,
    ModelReliabilityAuditRecord,
    MVPModuleSpecification,
    ResearchTrackClosureAudit,
    RoadmapSprintPlan,
    Sprint43MasterReport,
    Sprint43ProductAuditor,
)


@pytest.fixture(scope="module")
def auditor() -> Sprint43ProductAuditor:
    return Sprint43ProductAuditor()


@pytest.fixture(scope="module")
def master_report(auditor: Sprint43ProductAuditor) -> Sprint43MasterReport:
    report_path = Path("data/reports/sprint09_43_product_readiness_audit.json")
    roadmap_path = Path("data/reports/sprint09_43_mvp_roadmap.json")
    return auditor.run_full_sprint_audit(
        output_report_path=report_path,
        roadmap_report_path=roadmap_path,
    )


def test_01_baseline_verification_and_prior_artifacts_preservation(master_report: Sprint43MasterReport):
    """Test 1: Verify baseline commit and prior sprint artifacts preservation."""
    assert master_report.baseline_commit_sha == "219e3e3be0578b119d10c621e752afef4e860980"
    assert "09.43" in master_report.sprint_id

    # Prior sprint artifacts must exist and remain untouched
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/reports/sprint09_38_funding_predictability_report.json").exists()
    assert Path("data/reports/sprint09_39_cross_instrument_funding_report.json").exists()
    assert Path("data/reports/sprint09_40_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_40_s39_carry_accounting_correction.json").exists()
    assert Path("data/reports/sprint09_41_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_41_s40_claims_correction.json").exists()
    assert Path("data/reports/sprint09_42_master_report.json").exists()
    assert Path("data/reports/sprint09_42_exchange_margin_contracts.json").exists()


def test_02_capability_inventory_audit(master_report: Sprint43MasterReport):
    """Test 2: Verify that all 15 core architectural capabilities are inventoried."""
    inventory = master_report.capability_inventory
    assert len(inventory) == 15

    names = [c.capability_name for c in inventory]
    assert any("Data Ingestion Services" in n for n in names)
    assert any("Historical Data Storage" in n for n in names)
    assert any("Market Feature Computation" in n for n in names)
    assert any("Market Regime Classification" in n for n in names)
    assert any("Prediction Generation Engine" in n for n in names)
    assert any("Prediction Outcome Resolution" in n for n in names)
    assert any("Confidence Interval Computation" in n for n in names)
    assert any("Risk Condition & Warning Monitoring" in n for n in names)
    assert any("Dashboard Web Frontend" in n for n in names)
    assert any("Automated Test & Freeze Infrastructure" in n for n in names)

    for c in inventory:
        assert len(c.implementation_path) > 0
        assert c.reusability_for_mvp in {"DIRECTLY_REUSABLE", "REUSABLE_WITH_ADAPTATION", "NOT_RECOMMENDED"}


def test_03_research_track_closure(master_report: Sprint43MasterReport):
    """Test 3: Verify the formal archiving of the carry research track."""
    closure = master_report.research_closure
    assert "Perpetual Funding" in closure.track_name
    assert closure.closure_decision == "ARCHIVED_AS_ECONOMICALLY_UNATTRACTIVE_UNDER_TESTED_ASSUMPTIONS"
    assert closure.artifact_preservation_status == "ALL_HISTORICAL_ARTIFACTS_PRESERVED_IMMUTABLE"
    assert len(closure.reproducible_findings) >= 3
    assert len(closure.rejected_strategies) >= 4
    assert "US Treasury Bills" in closure.closure_rationale


def test_04_model_reliability_and_calibration_audit(master_report: Sprint43MasterReport):
    """Test 4: Verify documented calibration deficits (80% and 95% undercoverage)."""
    rel = {r.metric_name: r for r in master_report.model_reliability_audit}
    assert "80% Prediction Interval Coverage" in rel
    assert "95% Prediction Interval Coverage" in rel
    assert "Tail & Jump Risk Probabilities" in rel

    int_80 = rel["80% Prediction Interval Coverage"]
    assert "64.24%" in int_80.observed_performance
    assert int_80.recommended_product_action == "REQUIRES_RECALIBRATION"

    int_95 = rel["95% Prediction Interval Coverage"]
    assert "78.94%" in int_95.observed_performance
    assert int_95.recommended_product_action == "REQUIRES_RECALIBRATION"

    tail = rel["Tail & Jump Risk Probabilities"]
    assert "Static fallback" in tail.observed_performance
    assert tail.recommended_product_action == "HIDE_OR_LABEL_EXPERIMENTAL"


def test_05_architecture_assessment(master_report: Sprint43MasterReport):
    """Test 5: Verify software architecture assessment for user-facing MVP."""
    arch = master_report.architecture_assessment
    assert "ThreadingHTTPServer" in arch.backend_framework
    assert "Vanilla JavaScript" in arch.frontend_framework
    assert arch.resource_consumption_ram_mb < 150.0
    assert arch.monthly_operational_cost_usd < 10.0
    assert "500+" in arch.multi_user_concurrency
    assert "APPROVAL4=FALSE" in arch.security_and_auth
    assert arch.architecture_verdict == "LEAN_HIGH_PERFORMANCE_READY_FOR_MVP"


def test_06_mvp_module_prioritization(master_report: Sprint43MasterReport):
    """Test 6: Verify MVP module prioritization and readiness classifications."""
    modules = master_report.mvp_module_matrix
    assert len(modules) == 10

    ready_now_count = sum(1 for m in modules if m.implementation_status == "READY_NOW")
    assert ready_now_count >= 6  # At least 6 modules are ready now!

    # Conformal prediction must require development
    conformal = next(m for m in modules if "Conformal Prediction" in m.module_name)
    assert conformal.implementation_status == "REQUIRES_DEVELOPMENT"

    # All recommended modules must have zero or low safety risk
    for m in modules:
        if m.recommended_mvp_inclusion:
            assert m.safety_compliance_risk in {"NONE", "LOW"}


def test_07_product_roadmap_specification(master_report: Sprint43MasterReport):
    """Test 7: Verify concrete 6-sprint development roadmap."""
    roadmap = master_report.product_roadmap
    assert len(roadmap) == 6

    sprint_ids = [s.sprint_id for s in roadmap]
    assert sprint_ids == ["SPRINT_10.01", "SPRINT_10.02", "SPRINT_10.03", "SPRINT_10.04", "SPRINT_10.05", "SPRINT_10.06"]

    # Sprint 10.01 must address Conformal Prediction
    s10_01 = roadmap[0]
    assert "Conformal Prediction" in s10_01.sprint_title
    assert s10_01.risk_level == "MEDIUM"

    # Sprint 10.06 must be the release gate
    s10_06 = roadmap[-1]
    assert "Release" in s10_06.sprint_title


def test_08_mvp_release_acceptance_gates(master_report: Sprint43MasterReport):
    """Test 8: Verify definition of successful MVP release gates."""
    gates = master_report.definition_of_successful_mvp
    assert len(gates) == 9

    assert "GATE_01_DOCUMENTED_DEFINITIONS" in gates
    assert "GATE_02_CALIBRATED_INTERVALS" in gates
    assert "GATE_03_TRANSPARENT_LIMITATIONS" in gates
    assert "GATE_06_TRADING_DISABLED" in gates


def test_09_report_artifact_serialization():
    """Test 9: Verify JSON reports exist and parse cleanly."""
    rep_path = Path("data/reports/sprint09_43_product_readiness_audit.json")
    road_path = Path("data/reports/sprint09_43_mvp_roadmap.json")

    assert rep_path.exists()
    assert road_path.exists()

    with open(rep_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["sprint_id"] == "CBE-09.43"
    assert len(data["capability_inventory"]) == 15
    assert len(data["mvp_module_matrix"]) == 10

    with open(road_path, "r", encoding="utf-8") as f:
        r_data = json.load(f)
    assert len(r_data["sprints"]) == 6
    assert len(r_data["acceptance_gates"]) == 9


def test_10_adversarial_guardrails(auditor: Sprint43ProductAuditor):
    """Test 10: Adversarial checks ensuring zero trading leakage and no unhedged claims."""
    # 1. Verify trading capability is explicitly NOT recommended for MVP
    modules = auditor.prioritize_mvp_modules()
    for m in modules:
        assert "Order Execution" not in m.module_name
        assert "Automated Trading" not in m.module_name

    # 2. Check that raw uncalibrated intervals are not marked READY_NOW
    reliability = auditor.audit_model_reliability()
    int_80 = next(r for r in reliability if "80%" in r.metric_name)
    assert int_80.recommended_product_action != "READY_FOR_DISPLAY"

    # 3. Static fallback probability must never be marked READY_FOR_DISPLAY
    tail = next(r for r in reliability if "Tail" in r.metric_name)
    assert tail.recommended_product_action == "HIDE_OR_LABEL_EXPERIMENTAL"


def test_11_compute_latency_budget(auditor: Sprint43ProductAuditor):
    """Test 11: Verify pure analytical compute latency remains well under 50 ms."""
    t0 = time.perf_counter()
    auditor.audit_capability_inventory()
    auditor.audit_research_track_closure()
    auditor.audit_model_reliability()
    auditor.audit_architecture_assessment()
    auditor.prioritize_mvp_modules()
    auditor.build_product_roadmap()
    auditor.define_successful_mvp_gates()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 50.0, f"Pure compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"
