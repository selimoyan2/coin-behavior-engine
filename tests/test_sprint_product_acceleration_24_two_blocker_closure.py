"""
Sprint 24 Final Two-Blocker Closure Acceptance Tests.

Coin Behavior Engine (CBE) - Product Acceleration Sprint 24 Two-Blocker Closure.
Mandatory P0 Scientific Integrity & Evidence-Backed Verification:
1. Genuine Temporal Observation Overlap Algorithm (12 mandatory tests)
2. Grounded Scientific Status Verification (RES-MACRO-01, RES-DURABILITY-01, RES-REGIME-01, RES-ANALOG-01)
3. Saved Comparison Dynamic Re-validation
4. End-to-End API and Governance Invariants
"""

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
    ResearchRecord,
    RecordStatus,
    SignatureStatus,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    ResearchWorkspaceV2Engine,
    calculate_temporal_observation_overlap,
    normalize_iso_utc_timestamp,
    COMPARISON_METRIC_REGISTRY,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


class TestSprint24Blocker1GenuineTemporalObservationOverlap:
    """Comprehensive test suite covering the 12 mandatory temporal observation overlap conditions."""

    # -------------------------------------------------------------------------
    # Test 1: Same nominal window, disjoint real observations (intersection = 0)
    # -------------------------------------------------------------------------
    def test_01_same_nominal_window_different_real_observations(self):
        """Candidates sharing identical nominal window but having non-overlapping observations must fail closed."""
        # 100 odd-hour timestamps vs 100 even-hour timestamps within same 200h window
        ts_a = [f"2024-01-{(i * 2 + 1) // 24 + 1:02d}T{(i * 2 + 1) % 24:02d}:00:00Z" for i in range(100)]
        ts_b = [f"2024-01-{(i * 2) // 24 + 1:02d}T{(i * 2) % 24:02d}:00:00Z" for i in range(100)]

        r1 = ResearchRecord(
            id="RES-ODD-01", title="Odd Hours", title_en="Odd Hours", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-01-15T00:00:00Z",
            observed_timestamps=ts_a, sample_size=100
        )
        r2 = ResearchRecord(
            id="RES-EVEN-01", title="Even Hours", title_en="Even Hours", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-01-15T00:00:00Z",
            observed_timestamps=ts_b, sample_size=100
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DISJOINT_OBSERVATION_WINDOWS"
        assert res["shared_interval_count"] == 0

    # -------------------------------------------------------------------------
    # Test 2: Disjoint observation timestamp sets
    # -------------------------------------------------------------------------
    def test_02_disjoint_timestamp_sets(self):
        """Timestamp sets in disjoint months must fail closed with DISJOINT_OBSERVATION_WINDOWS."""
        ts_jan = [f"2024-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        ts_feb = [f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]

        r1 = ResearchRecord(
            id="RES-JAN-01", title="Jan Data", title_en="Jan Data", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-01-10T00:00:00Z",
            observed_timestamps=ts_jan, sample_size=120
        )
        r2 = ResearchRecord(
            id="RES-FEB-01", title="Feb Data", title_en="Feb Data", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-02-01T00:00:00Z", observation_end_utc="2024-02-10T00:00:00Z",
            observed_timestamps=ts_feb, sample_size=120
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DISJOINT_OBSERVATION_WINDOWS"
        assert res["shared_interval_count"] == 0

    # -------------------------------------------------------------------------
    # Test 3: Exactly 99 shared observations (fails floor >= 100)
    # -------------------------------------------------------------------------
    def test_03_exactly_99_shared_observations_fails_floor(self):
        """Candidate pair sharing exactly 99 timestamps must fail closed with INSUFFICIENT_OVERLAP."""
        base_ts = [f"2024-03-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(99)]
        ts_1 = base_ts + ["2024-03-20T00:00:00Z"]
        ts_2 = base_ts + ["2024-03-21T00:00:00Z"]

        r1 = ResearchRecord(
            id="RES-99-A", title="99 A", title_en="99 A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-03-01T00:00:00Z", observation_end_utc="2024-03-25T00:00:00Z",
            observed_timestamps=ts_1, sample_size=100
        )
        r2 = ResearchRecord(
            id="RES-99-B", title="99 B", title_en="99 B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-03-01T00:00:00Z", observation_end_utc="2024-03-25T00:00:00Z",
            observed_timestamps=ts_2, sample_size=100
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP"
        assert res["shared_interval_count"] == 99

    # -------------------------------------------------------------------------
    # Test 4: Exactly 100 shared observations (passes floor >= 100)
    # -------------------------------------------------------------------------
    def test_04_exactly_100_shared_observations_passes(self):
        """Candidate pair sharing exactly 100 timestamps must pass floor validation."""
        shared_100 = [f"2024-03-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(100)]

        r1 = ResearchRecord(
            id="RES-100-A", title="100 A", title_en="100 A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-03-01T00:00:00Z", observation_end_utc="2024-03-25T00:00:00Z",
            observed_timestamps=shared_100, sample_size=100
        )
        r2 = ResearchRecord(
            id="RES-100-B", title="100 B", title_en="100 B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-03-01T00:00:00Z", observation_end_utc="2024-03-25T00:00:00Z",
            observed_timestamps=shared_100, sample_size=100
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 100
        assert res["overlap_start_utc"] == shared_100[0]
        assert res["overlap_end_utc"] == shared_100[-1]

    # -------------------------------------------------------------------------
    # Test 5: Exactly 101 shared observations (passes floor >= 100)
    # -------------------------------------------------------------------------
    def test_05_exactly_101_shared_observations_passes(self):
        """Candidate pair sharing exactly 101 timestamps must pass floor validation."""
        shared_101 = [f"2024-03-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(101)]

        r1 = ResearchRecord(
            id="RES-101-A", title="101 A", title_en="101 A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-03-01T00:00:00Z", observation_end_utc="2024-03-25T00:00:00Z",
            observed_timestamps=shared_101, sample_size=101
        )
        r2 = ResearchRecord(
            id="RES-101-B", title="101 B", title_en="101 B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-03-01T00:00:00Z", observation_end_utc="2024-03-25T00:00:00Z",
            observed_timestamps=shared_101, sample_size=101
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 101

    # -------------------------------------------------------------------------
    # Test 6: Duplicated timestamps in observation series
    # -------------------------------------------------------------------------
    def test_06_duplicated_timestamps_rejected(self):
        """Candidate containing non-unique timestamps fails closed with DUPLICATED_OBSERVATIONS_DETECTED."""
        ts_valid = [f"2024-04-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        ts_dup = ts_valid.copy()
        ts_dup[10] = ts_dup[9]  # Duplicate injection

        r1 = ResearchRecord(
            id="RES-DUP-A", title="Dup A", title_en="Dup A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-04-01T00:00:00Z", observation_end_utc="2024-04-10T00:00:00Z",
            observed_timestamps=ts_dup, sample_size=120
        )
        r2 = ResearchRecord(
            id="RES-DUP-B", title="Dup B", title_en="Dup B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-04-01T00:00:00Z", observation_end_utc="2024-04-10T00:00:00Z",
            observed_timestamps=ts_valid, sample_size=120
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DUPLICATED_OBSERVATIONS_DETECTED"

    # -------------------------------------------------------------------------
    # Test 7: Missing hourly intervals (nominal 150 hours, actual 90 observations)
    # -------------------------------------------------------------------------
    def test_07_missing_hourly_observations_below_floor_fails(self):
        """Nominal 150h duration with 60 missing intervals yields 90 actual shared observations and fails."""
        # 150 hours window, but only 90 timestamps actually recorded (60 gaps)
        ts_sparse = [f"2024-05-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(90)]

        r1 = ResearchRecord(
            id="RES-SPARSE-A", title="Sparse A", title_en="Sparse A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-05-01T00:00:00Z", observation_end_utc="2024-05-07T06:00:00Z",  # 150h window
            observed_timestamps=ts_sparse, sample_size=90
        )
        r2 = ResearchRecord(
            id="RES-SPARSE-B", title="Sparse B", title_en="Sparse B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-05-01T00:00:00Z", observation_end_utc="2024-05-07T06:00:00Z",
            observed_timestamps=ts_sparse, sample_size=90
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP"
        assert res["shared_interval_count"] == 90

    # -------------------------------------------------------------------------
    # Test 8: Different UTC representations ('Z' vs '+03:00') normalized
    # -------------------------------------------------------------------------
    def test_08_differing_utc_representations_normalized_and_matched(self):
        """Candidate A with 'Z' and Candidate B with '+03:00' representing the same instants pass correctly."""
        # Candidate A in Zulu (UTC)
        ts_zulu = [f"2024-06-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(110)]
        # Candidate B in UTC+3 (same instants shifted by +3h in local representation)
        ts_utc3 = []
        for i in range(110):
            # Same instant in +03:00
            hour_utc = i % 24
            day_utc = (i // 24) + 1
            dt_utc = datetime(2024, 6, day_utc, hour_utc, 0, 0, tzinfo=timezone.utc)
            from datetime import timedelta
            tz_plus3 = timezone(timedelta(hours=3))
            dt_plus3 = dt_utc.astimezone(tz_plus3)
            ts_utc3.append(dt_plus3.isoformat())

        r1 = ResearchRecord(
            id="RES-UTC-Z", title="UTC Z", title_en="UTC Z", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-06-01T00:00:00Z", observation_end_utc="2024-06-10T00:00:00Z",
            observed_timestamps=ts_zulu, sample_size=110
        )
        r2 = ResearchRecord(
            id="RES-UTC-P3", title="UTC +3", title_en="UTC +3", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-06-01T03:00:00+03:00", observation_end_utc="2024-06-10T03:00:00+03:00",
            observed_timestamps=ts_utc3, sample_size=110
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 110

    # -------------------------------------------------------------------------
    # Test 9: Invalid timestamp strings fail closed
    # -------------------------------------------------------------------------
    def test_09_invalid_timestamp_strings_rejected(self):
        """Candidate containing unparseable timestamp string fails closed."""
        ts_invalid = [f"2024-07-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(105)]
        ts_invalid[50] = "2024-99-99T99:99:99Z"  # Malformed

        r1 = ResearchRecord(
            id="RES-INV-1", title="Inv 1", title_en="Inv 1", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-07-01T00:00:00Z", observation_end_utc="2024-07-10T00:00:00Z",
            observed_timestamps=ts_invalid, sample_size=105
        )
        r2 = ResearchRecord(
            id="RES-INV-2", title="Inv 2", title_en="Inv 2", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-07-01T00:00:00Z", observation_end_utc="2024-07-10T00:00:00Z",
            observed_timestamps=[f"2024-07-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(105)],
            sample_size=105
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP_EVIDENCE"

    # -------------------------------------------------------------------------
    # Test 10: Records with start/end metadata only (no observation list / attestation)
    # -------------------------------------------------------------------------
    def test_10_start_end_metadata_only_rejected_insufficient_evidence(self):
        """Records with nominal start/end but lacking observation series and completeness attestation fail closed."""
        r1 = ResearchRecord(
            id="RES-META-ONLY-1", title="Meta Only 1", title_en="Meta Only 1", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-08-01T00:00:00Z", observation_end_utc="2024-08-20T00:00:00Z",
            observed_timestamps=None, sample_size=450
        )
        r2 = ResearchRecord(
            id="RES-META-ONLY-2", title="Meta Only 2", title_en="Meta Only 2", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-08-01T00:00:00Z", observation_end_utc="2024-08-20T00:00:00Z",
            observed_timestamps=None, sample_size=450
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP_EVIDENCE"

    # -------------------------------------------------------------------------
    # Test 11: One candidate missing observation list
    # -------------------------------------------------------------------------
    def test_11_one_candidate_missing_observation_list_fails_closed(self):
        """If one candidate has explicit timestamps but the second candidate lacks them, gate fails closed."""
        ts_valid = [f"2024-09-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]

        r1 = ResearchRecord(
            id="RES-HAS-LIST", title="Has List", title_en="Has List", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-09-01T00:00:00Z", observation_end_utc="2024-09-10T00:00:00Z",
            observed_timestamps=ts_valid, sample_size=120
        )
        r2 = ResearchRecord(
            id="RES-NO-LIST", title="No List", title_en="No List", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-09-01T00:00:00Z", observation_end_utc="2024-09-10T00:00:00Z",
            observed_timestamps=None, sample_size=120
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP_EVIDENCE"

    # -------------------------------------------------------------------------
    # Test 12: Sufficient overlap (>= 100) but metric contract mismatch
    # -------------------------------------------------------------------------
    def test_12_sufficient_overlap_but_metric_definition_mismatch(self, monkeypatch):
        """When temporal overlap is valid (N=120) but candidates share no compatible metric contract, gate fails."""
        sample_ts = [f"2024-10-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]

        # r1 provides volatility_ratio
        r1 = ResearchRecord(
            id="RES-METRIC-A", title="Metric A", title_en="Metric A", category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026", historical_period="2024-10-01 to 2024-10-10",
            window_cadence="1h", specification_id="SP-A",
            observation_start_utc="2024-10-01T00:00:00Z", observation_end_utc="2024-10-10T00:00:00Z",
            observed_timestamps=sample_ts, sample_size=120,
            volatility_ratio=1.250, evidence_status="SIGNED_VALID"
        )
        # r2 provides observed_mean_funding_bps (completely different metric, volatility_ratio is None)
        r2 = ResearchRecord(
            id="RES-METRIC-B", title="Metric B", title_en="Metric B", category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026", historical_period="2024-10-01 to 2024-10-10",
            window_cadence="1h", specification_id="SP-B",
            observation_start_utc="2024-10-01T00:00:00Z", observation_end_utc="2024-10-10T00:00:00Z",
            observed_timestamps=sample_ts, sample_size=120,
            volatility_ratio=None, observed_metrics={"observed_mean_funding_bps": 1.05},
            evidence_status="SIGNED_VALID"
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-METRIC-A", "RES-METRIC-B"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "METRIC_DEFINITION_MISMATCH"
        assert res["difference_analysis"] == []


class TestSprint24Blocker2EvidenceBackedScientificStatuses:
    """Verifies that scientific statuses in ResearchCatalogProvider are grounded in evidence without fabrication."""

    def test_res_macro_01_status_downgrade(self):
        """RES-MACRO-01 has no independent replication; must be REPLICATION_NOT_ESTABLISHED and UNVERIFIED."""
        records = ResearchCatalogProvider.load_catalog(force_reload=True)
        macro = next(r for r in records if r.id == "RES-MACRO-01")

        assert macro.replication_verdict == "REPLICATION_NOT_ESTABLISHED"
        assert macro.record_status == RecordStatus.UNVERIFIED
        assert macro.validation_status == "UNVERIFIED"
        assert macro.evidence_status == "UNSIGNED"
        assert macro.scientific_eligibility == "ELIGIBLE"
        assert macro.quarantine_status == "CLEAR"

    def test_res_durability_01_operational_attestation_status(self):
        """RES-DURABILITY-01 is operational benchmark log; must be INELIGIBLE, NOT_APPLICABLE, OPERATIONAL_AUDIT_LOG."""
        records = ResearchCatalogProvider.load_catalog(force_reload=True)
        dur = next(r for r in records if r.id == "RES-DURABILITY-01")

        assert dur.scientific_eligibility == "INELIGIBLE"
        assert dur.record_status == RecordStatus.UNVERIFIED
        assert dur.validation_status == "OPERATIONAL_AUDIT_LOG"
        assert dur.replication_verdict == "NOT_APPLICABLE"
        assert dur.evidence_status == "UNSIGNED"

    def test_res_regime_and_analog_unverified_replication(self):
        """RES-REGIME-01 and RES-ANALOG-01 have no independent replications; must be REPLICATION_NOT_ESTABLISHED."""
        records = ResearchCatalogProvider.load_catalog(force_reload=True)
        regime = next(r for r in records if r.id == "RES-REGIME-01")
        analog = next(r for r in records if r.id == "RES-ANALOG-01")

        assert regime.replication_verdict == "REPLICATION_NOT_ESTABLISHED"
        assert regime.record_status == RecordStatus.UNVERIFIED
        assert regime.validation_status == "UNVERIFIED"

        assert analog.replication_verdict == "REPLICATION_NOT_ESTABLISHED"
        assert analog.record_status == RecordStatus.UNVERIFIED
        assert analog.validation_status == "UNVERIFIED"

    def test_summary_counts_truthful_zero_confirmed_replications(self):
        """Summary counts must report 0 confirmed replications and 0 verified findings across historical catalog."""
        counts = ResearchCatalogProvider.get_catalog_summary_counts()
        assert counts["total_catalog_records"] >= 6
        assert counts["verified_scientific_findings"] == 0
        assert counts["independent_replications"] == 0
        assert counts["unverified_records"] >= 5
        assert counts["quarantined_records"] >= 2  # RES-CRYPTO-01 (quarantined) + RES-DURABILITY-01 (ineligible)

    def test_reconciliation_matrix_reflects_downgraded_statuses(self):
        """Reconciliation matrix must document exact downgrade reasons for all audited records."""
        matrix = ResearchCatalogProvider.get_reconciliation_matrix()
        rec_map = {m.record_id: m for m in matrix}

        assert "RES-MACRO-01" in rec_map
        assert "REPLICATION_NOT_ESTABLISHED" in rec_map["RES-MACRO-01"].downgrade_reason
        assert rec_map["RES-MACRO-01"].final_accepted_status == RecordStatus.UNVERIFIED

        assert "RES-DURABILITY-01" in rec_map
        assert "OPERATIONAL_AUDIT_LOG" in rec_map["RES-DURABILITY-01"].downgrade_reason
        assert rec_map["RES-DURABILITY-01"].final_accepted_status == RecordStatus.UNVERIFIED


class TestSprint24SavedComparisonLiveRevalidation:
    """Verifies that saved comparisons are re-evaluated live against current strict gates upon retrieval."""

    def test_saved_comparison_revalidated_live(self, tmp_path, monkeypatch):
        """Saved comparison referencing records without timestamps fails live revalidation."""
        monkeypatch.setenv("CBE_SAVED_COMPARISONS_PATH", str(tmp_path))

        # Records without timestamps saved
        r1 = ResearchRecord(
            id="RES-COMPAT-01", title="Comp 1", title_en="Comp 1", category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026", historical_period="2024-01-01 to 2024-06-01",
            window_cadence="1h", specification_id="SPEC-002-WF",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z",
            volatility_ratio=1.240, evidence_status="SIGNED_VALID"
        )
        r2 = ResearchRecord(
            id="RES-COMPAT-02", title="Comp 2", title_en="Comp 2", category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026", historical_period="2024-02-01 to 2024-06-01",
            window_cadence="1h", specification_id="SPEC-003-AM",
            observation_start_utc="2024-02-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z",
            volatility_ratio=1.310, evidence_status="SIGNED_VALID"
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        # Create raw saved file representing legacy comparison without timestamps
        legacy_comp = {
            "comparison_id": "CMP-LEGACY-001",
            "title": "Legacy Saved Comp",
            "candidate_ids": ["RES-COMPAT-01", "RES-COMPAT-02"],
            "created_at_utc": "2026-10-25T12:00:00Z",
            "is_compatible": True,  # Previously saved as True
            "difference_analysis": [{"pair": "RES-COMPAT-01 vs RES-COMPAT-02", "metrics": {}}],
        }
        fpath = tmp_path / "CMP-LEGACY-001.json"
        fpath.write_text(json.dumps(legacy_comp), encoding="utf-8")

        # Load via get_saved_comparison: live revalidation must catch lack of timestamps
        loaded = ResearchWorkspaceV2Engine.get_saved_comparison("CMP-LEGACY-001")
        assert loaded is not None
        assert loaded["is_compatible"] is False
        assert loaded["validation_status"] == "REVALIDATION_FAILED"
        assert loaded["rejection_code"] == "INSUFFICIENT_OVERLAP_EVIDENCE"
        assert loaded["difference_analysis"] == []
