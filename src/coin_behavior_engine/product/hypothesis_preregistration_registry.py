"""Scientific Hypothesis Registry & Preregistration Engine (Module 28.2).

Prevents retrospective hypothesis rewriting, post-hoc data mining, and
uncontrolled research selection:
- Canonical hypothesis registration schema.
- Immutable canonical preregistration snapshots with RFC-8785 style deterministic serialization.
- Append-only amendment history.
- Retrospective registration detection and tagging (RETROSPECTIVE_REGISTRATION).
- Confirmatory eligibility gate enforcement.
- Durable multiprocess-safe JSON persistence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PERSISTENCE_PATH = REPO_ROOT / "data" / "research_lab" / "hypothesis_registry.json"

VALID_HYPOTHESIS_LIFECYCLE: Set[str] = {
    "DRAFT",
    "EXPLORATORY",
    "PREREGISTERED",
    "VALIDATION_PENDING",
    "VALIDATION_IN_PROGRESS",
    "VALIDATION_COMPLETED",
    "CONFIRMATORY_EVIDENCE_AVAILABLE",
    "INCONCLUSIVE",
    "REJECTED",
    "BLOCKED",
}


@dataclass
class HypothesisAmendment:
    """Append-only amendment record for a preregistered hypothesis."""
    amendment_id: str
    hypothesis_id: str
    amendment_reason: str
    changed_fields: Dict[str, Any]
    amendment_timestamp: str
    amendment_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScientificHypothesisRecord:
    """Canonical research hypothesis record."""
    hypothesis_id: str
    research_id: str
    hypothesis_title: str
    scientific_question: str
    null_hypothesis: str
    alternative_hypothesis: str
    target_population: str
    target_metric: str
    effect_definition: str
    expected_effect_direction: str
    dataset_eligibility_rules: Dict[str, Any]
    training_period: Dict[str, str]
    validation_period: Dict[str, str]
    holdout_period: Dict[str, str]
    statistical_test_plan: Dict[str, Any]
    multiple_testing_family_id: str
    minimum_sample_requirements: Dict[str, int]
    missing_data_policy: str
    preregistration_status: str
    preregistration_timestamp: Optional[str]
    preregistration_digest: Optional[str]
    is_retrospective: bool = False
    retrospective_justification: Optional[str] = None
    canonical_snapshot: Optional[Dict[str, Any]] = None
    amendments: List[HypothesisAmendment] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["amendments"] = [a.to_dict() if hasattr(a, "to_dict") else a for a in self.amendments]
        return data


class HypothesisPreregistrationRegistry:
    """Registry managing hypothesis creation, immutable preregistration snapshots,

    amendments, and confirmatory gate validation.
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        self.persistence_path = persistence_path or DEFAULT_PERSISTENCE_PATH
        self._hypotheses: Dict[str, ScientificHypothesisRecord] = {}
        self._load_from_storage()
        if not self._hypotheses:
            self._seed_canonical_hypotheses()

    @staticmethod
    def compute_canonical_digest(data: Dict[str, Any]) -> str:
        """Deterministic RFC-8785 style JSON serialization and SHA-256 hash."""
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _load_from_storage(self) -> None:
        """Load registered hypotheses from disk."""
        if not self.persistence_path.exists():
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            hyp_list = raw_data.get("hypotheses", [])
            for item in hyp_list:
                amendments = [
                    HypothesisAmendment(**a) if isinstance(a, dict) else a
                    for a in item.get("amendments", [])
                ]
                item_copy = dict(item)
                item_copy["amendments"] = amendments
                rec = ScientificHypothesisRecord(**item_copy)
                self._hypotheses[rec.hypothesis_id] = rec
        except Exception as e:
            logger.error(f"Failed to load hypothesis registry: {e}")

    def save_to_storage(self) -> None:
        """Atomically persist hypothesis registry to disk."""
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.persistence_path.with_suffix(".tmp")
        payload = {
            "schema_version": "CBE-HYPOTHESIS-REGISTRY-V28",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "hypotheses": [h.to_dict() for h in self._hypotheses.values()],
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp_path.replace(self.persistence_path)

    def _seed_canonical_hypotheses(self) -> None:
        """Seed foundational scientific hypotheses grounded in historical BTC research."""
        seeds = [
            {
                "hypothesis_id": "HYP-VOL-PERSIST-001",
                "research_id": "RES-STAT-02",
                "hypothesis_title": "Historical BTC Volatility Clustering Persistence",
                "scientific_question": "Does historical BTC return volatility exhibit statistically significant autoregressive clustering across quarterly regimes?",
                "null_hypothesis": "Historical BTC returns exhibit independent and identically distributed variance with zero autoregressive persistence (ARCH coefficient = 0).",
                "alternative_hypothesis": "Historical BTC return variance exhibits significant volatility clustering (ARCH effect p < 0.01).",
                "target_population": "BTC/USDT Spot Hourly Bars (2024-01-01 to 2024-12-31)",
                "target_metric": "ARCH_LM_STATISTIC",
                "effect_definition": "Lag-1 autoregressive coefficient of squared returns",
                "expected_effect_direction": "POSITIVE",
                "dataset_eligibility_rules": {"instruments": ["BTC/USDT"], "cadences": ["1h", "15m"], "markets": ["BINANCE"]},
                "training_period": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-30T23:59:59Z"},
                "validation_period": {"start": "2024-07-01T00:00:00Z", "end": "2024-09-30T23:59:59Z"},
                "holdout_period": {"start": "2024-10-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "statistical_test_plan": {"test_name": "ENGLE_ARCH_LM_TEST", "alpha": 0.01, "alternative": "two-sided"},
                "multiple_testing_family_id": "FAM-VOL-DYNAMICS-01",
                "minimum_sample_requirements": {"min_observations": 1000},
                "missing_data_policy": "FAIL_CLOSED_IF_GAPS_EXCEED_2_PERCENT",
                "preregistration_status": "PREREGISTERED",
                "preregistration_timestamp": "2024-01-01T00:00:00Z",
                "is_retrospective": False,
            },
            {
                "hypothesis_id": "HYP-REG-SHIFT-002",
                "research_id": "RES-GEN-05",
                "hypothesis_title": "Cross-Regime Volatility Distribution Shift",
                "scientific_question": "Do return distributions differ significantly between high-volatility and low-volatility historical regimes?",
                "null_hypothesis": "The return distributions in high-volatility and low-volatility regimes are identical (Kolmogorov-Smirnov p >= 0.05).",
                "alternative_hypothesis": "The return distributions differ significantly across regimes (KS p < 0.05).",
                "target_population": "BTC/USDT Spot 15m Bars (2024 Q1-Q4)",
                "target_metric": "KS_DISTANCE",
                "effect_definition": "Two-sample Kolmogorov-Smirnov supremum distance",
                "expected_effect_direction": "POSITIVE",
                "dataset_eligibility_rules": {"instruments": ["BTC/USDT"], "cadences": ["15m"], "markets": ["BINANCE"]},
                "training_period": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-30T23:59:59Z"},
                "validation_period": {"start": "2024-07-01T00:00:00Z", "end": "2024-09-30T23:59:59Z"},
                "holdout_period": {"start": "2024-10-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "statistical_test_plan": {"test_name": "KOLMOGOROV_SMIRNOV_2SAMPLE", "alpha": 0.05, "alternative": "two-sided"},
                "multiple_testing_family_id": "FAM-REGIME-DIST-01",
                "minimum_sample_requirements": {"min_observations": 2000},
                "missing_data_policy": "RECORD_GAPS_AND_EXCLUDE",
                "preregistration_status": "PREREGISTERED",
                "preregistration_timestamp": "2024-01-01T00:00:00Z",
                "is_retrospective": False,
            },
            {
                "hypothesis_id": "HYP-RETRO-ANALOG-003",
                "research_id": "RES-HIST-01",
                "hypothesis_title": "Retrospective Analog Pattern Correlation Analysis",
                "scientific_question": "Does analog historical similarity predict short-term return directionality?",
                "null_hypothesis": "Historical analog matches exhibit random future directional distribution.",
                "alternative_hypothesis": "Analog matches exhibit directional bias.",
                "target_population": "BTC/USDT Spot Multiyear 2022-2023",
                "target_metric": "DIRECTIONAL_ACCURACY",
                "effect_definition": "Sign agreement between historical analog future and target future",
                "expected_effect_direction": "POSITIVE",
                "dataset_eligibility_rules": {"instruments": ["BTC/USDT"], "cadences": ["1h"], "markets": ["BINANCE"]},
                "training_period": {"start": "2022-01-01T00:00:00Z", "end": "2022-12-31T23:59:59Z"},
                "validation_period": {"start": "2023-01-01T00:00:00Z", "end": "2023-06-30T23:59:59Z"},
                "holdout_period": {"start": "2023-07-01T00:00:00Z", "end": "2023-12-31T23:59:59Z"},
                "statistical_test_plan": {"test_name": "BINOMIAL_SIGN_TEST", "alpha": 0.05},
                "multiple_testing_family_id": "FAM-ANALOG-01",
                "minimum_sample_requirements": {"min_observations": 500},
                "missing_data_policy": "STRICT_CHECK",
                "preregistration_status": "EXPLORATORY",
                "preregistration_timestamp": None,
                "is_retrospective": True,
                "retrospective_justification": "Formulated retrospectively after inspection of 2022-2023 market drawdown episodes.",
            },
        ]

        for s in seeds:
            # Generate canonical snapshot and digest for preregistered
            digest = None
            snap = None
            if s["preregistration_status"] == "PREREGISTERED":
                snap_payload = {
                    "hypothesis_id": s["hypothesis_id"],
                    "research_id": s["research_id"],
                    "hypothesis_title": s["hypothesis_title"],
                    "scientific_question": s["scientific_question"],
                    "null_hypothesis": s["null_hypothesis"],
                    "alternative_hypothesis": s["alternative_hypothesis"],
                    "target_metric": s["target_metric"],
                    "dataset_eligibility_rules": s["dataset_eligibility_rules"],
                    "training_period": s["training_period"],
                    "validation_period": s["validation_period"],
                    "holdout_period": s["holdout_period"],
                    "statistical_test_plan": s["statistical_test_plan"],
                    "multiple_testing_family_id": s["multiple_testing_family_id"],
                }
                digest = self.compute_canonical_digest(snap_payload)
                snap = snap_payload

            rec = ScientificHypothesisRecord(
                hypothesis_id=s["hypothesis_id"],
                research_id=s["research_id"],
                hypothesis_title=s["hypothesis_title"],
                scientific_question=s["scientific_question"],
                null_hypothesis=s["null_hypothesis"],
                alternative_hypothesis=s["alternative_hypothesis"],
                target_population=s["target_population"],
                target_metric=s["target_metric"],
                effect_definition=s["effect_definition"],
                expected_effect_direction=s["expected_effect_direction"],
                dataset_eligibility_rules=s["dataset_eligibility_rules"],
                training_period=s["training_period"],
                validation_period=s["validation_period"],
                holdout_period=s["holdout_period"],
                statistical_test_plan=s["statistical_test_plan"],
                multiple_testing_family_id=s["multiple_testing_family_id"],
                minimum_sample_requirements=s["minimum_sample_requirements"],
                missing_data_policy=s["missing_data_policy"],
                preregistration_status=s["preregistration_status"],
                preregistration_timestamp=s["preregistration_timestamp"],
                preregistration_digest=digest,
                is_retrospective=s["is_retrospective"],
                retrospective_justification=s.get("retrospective_justification"),
                canonical_snapshot=snap,
            )
            self._hypotheses[rec.hypothesis_id] = rec

        self.save_to_storage()

    def register_hypothesis(
        self,
        hypothesis_id: str,
        research_id: str,
        hypothesis_title: str,
        scientific_question: str,
        null_hypothesis: str,
        alternative_hypothesis: str,
        target_population: str,
        target_metric: str,
        effect_definition: str,
        expected_effect_direction: str,
        dataset_eligibility_rules: Dict[str, Any],
        training_period: Dict[str, str],
        validation_period: Dict[str, str],
        holdout_period: Dict[str, str],
        statistical_test_plan: Dict[str, Any],
        multiple_testing_family_id: str,
        minimum_sample_requirements: Dict[str, int],
        missing_data_policy: str = "FAIL_CLOSED_ON_GAPS",
        is_retrospective: bool = False,
        retrospective_justification: Optional[str] = None,
    ) -> ScientificHypothesisRecord:
        """Register a new hypothesis in DRAFT or EXPLORATORY status."""
        hyp_id = str(hypothesis_id or "").strip()
        if not hyp_id:
            raise ValueError("hypothesis_id is mandatory.")
        if hyp_id in self._hypotheses:
            raise ValueError(f"Hypothesis '{hyp_id}' is already registered.")

        status = "EXPLORATORY" if is_retrospective else "DRAFT"

        rec = ScientificHypothesisRecord(
            hypothesis_id=hyp_id,
            research_id=str(research_id),
            hypothesis_title=str(hypothesis_title),
            scientific_question=str(scientific_question),
            null_hypothesis=str(null_hypothesis),
            alternative_hypothesis=str(alternative_hypothesis),
            target_population=str(target_population),
            target_metric=str(target_metric),
            effect_definition=str(effect_definition),
            expected_effect_direction=str(expected_effect_direction),
            dataset_eligibility_rules=dataset_eligibility_rules,
            training_period=training_period,
            validation_period=validation_period,
            holdout_period=holdout_period,
            statistical_test_plan=statistical_test_plan,
            multiple_testing_family_id=str(multiple_testing_family_id),
            minimum_sample_requirements=minimum_sample_requirements,
            missing_data_policy=missing_data_policy,
            preregistration_status=status,
            preregistration_timestamp=None,
            preregistration_digest=None,
            is_retrospective=is_retrospective,
            retrospective_justification=retrospective_justification,
        )

        self._hypotheses[hyp_id] = rec
        self.save_to_storage()
        return rec

    def preregister_hypothesis(
        self,
        hypothesis_id: str,
        timestamp: Optional[str] = None,
    ) -> ScientificHypothesisRecord:
        """Lock and preregister a hypothesis with an immutable canonical snapshot.

        Retrospective hypotheses CANNOT be preregistered as prospective confirmatory studies.
        """
        hyp_id = str(hypothesis_id or "").strip()
        rec = self._hypotheses.get(hyp_id)
        if not rec:
            raise KeyError(f"Hypothesis '{hyp_id}' not found.")

        if rec.is_retrospective:
            raise ValueError(
                f"Hypothesis '{hyp_id}' is marked as RETROSPECTIVE_REGISTRATION and "
                "cannot be promoted to prospective PREREGISTERED status."
            )

        if rec.preregistration_status == "PREREGISTERED":
            raise ValueError(f"Hypothesis '{hyp_id}' is already preregistered.")

        ts = timestamp or datetime.now(timezone.utc).isoformat()

        snap_payload = {
            "hypothesis_id": rec.hypothesis_id,
            "research_id": rec.research_id,
            "hypothesis_title": rec.hypothesis_title,
            "scientific_question": rec.scientific_question,
            "null_hypothesis": rec.null_hypothesis,
            "alternative_hypothesis": rec.alternative_hypothesis,
            "target_metric": rec.target_metric,
            "dataset_eligibility_rules": rec.dataset_eligibility_rules,
            "training_period": rec.training_period,
            "validation_period": rec.validation_period,
            "holdout_period": rec.holdout_period,
            "statistical_test_plan": rec.statistical_test_plan,
            "multiple_testing_family_id": rec.multiple_testing_family_id,
        }

        digest = self.compute_canonical_digest(snap_payload)

        rec.preregistration_status = "PREREGISTERED"
        rec.preregistration_timestamp = ts
        rec.preregistration_digest = digest
        rec.canonical_snapshot = snap_payload
        rec.updated_at = datetime.now(timezone.utc).isoformat()

        self.save_to_storage()
        return rec

    def amend_preregistered_hypothesis(
        self,
        hypothesis_id: str,
        amendment_reason: str,
        changed_fields: Dict[str, Any],
    ) -> HypothesisAmendment:
        """Append an amendment without overwriting the original immutable snapshot."""
        hyp_id = str(hypothesis_id or "").strip()
        rec = self._hypotheses.get(hyp_id)
        if not rec:
            raise KeyError(f"Hypothesis '{hyp_id}' not found.")

        if rec.preregistration_status != "PREREGISTERED":
            raise ValueError(f"Hypothesis '{hyp_id}' must be in PREREGISTERED status to amend.")

        if not amendment_reason or not amendment_reason.strip():
            raise ValueError("Amendment reason is mandatory.")

        if not changed_fields:
            raise ValueError("changed_fields cannot be empty.")

        now_ts = datetime.now(timezone.utc).isoformat()
        amend_idx = len(rec.amendments) + 1
        amend_id = f"AMD-{hyp_id}-{amend_idx:03d}"

        amend_payload = {
            "amendment_id": amend_id,
            "hypothesis_id": hyp_id,
            "amendment_reason": amendment_reason,
            "changed_fields": changed_fields,
            "timestamp": now_ts,
        }
        amend_digest = self.compute_canonical_digest(amend_payload)

        amendment = HypothesisAmendment(
            amendment_id=amend_id,
            hypothesis_id=hyp_id,
            amendment_reason=amendment_reason,
            changed_fields=changed_fields,
            amendment_timestamp=now_ts,
            amendment_digest=amend_digest,
        )

        rec.amendments.append(amendment)
        rec.updated_at = now_ts
        self.save_to_storage()
        return amendment

    def evaluate_confirmatory_eligibility(
        self,
        hypothesis_id: str,
        evaluation_timestamp: str,
        methodology_id: str,
        statistical_test_name: str,
        dataset_provenance_status: str,
        multiple_testing_accounted: bool,
        reproducibility_status: str,
        has_uncertainty_measures: bool,
    ) -> Tuple[bool, str, List[str]]:
        """Confirmatory Gate Evaluation (Section 5.5).

        A hypothesis may receive confirmatory status ONLY when:
        1. Preregistration predates the evaluation timestamp.
        2. Hypothesis is not retrospective.
        3. Preregistration status is PREREGISTERED.
        4. Statistical test matches the preregistered plan.
        5. Multiple testing is accounted for.
        6. Dataset provenance is verified.
        7. Reproducibility is verified.
        8. Uncertainty measures are present.
        """
        hyp_id = str(hypothesis_id or "").strip()
        rec = self._hypotheses.get(hyp_id)
        if not rec:
            return False, "HYPOTHESIS_NOT_FOUND", [f"Hypothesis '{hyp_id}' not found."]

        blocking_reasons: List[str] = []

        if rec.is_retrospective:
            blocking_reasons.append("Hypothesis is retrospectively registered; barred from confirmatory status.")

        if rec.preregistration_status != "PREREGISTERED":
            blocking_reasons.append(f"Hypothesis status is '{rec.preregistration_status}', not PREREGISTERED.")

        if not rec.preregistration_timestamp:
            blocking_reasons.append("Missing preregistration timestamp.")
        else:
            try:
                prereg_dt = datetime.fromisoformat(rec.preregistration_timestamp.replace("Z", "+00:00"))
                eval_dt = datetime.fromisoformat(evaluation_timestamp.replace("Z", "+00:00"))
                if eval_dt <= prereg_dt:
                    blocking_reasons.append(
                        f"Evaluation timestamp ({evaluation_timestamp}) does not strictly postdate "
                        f"preregistration timestamp ({rec.preregistration_timestamp})."
                    )
            except Exception as e:
                blocking_reasons.append(f"Timestamp comparison error: {str(e)}")

        plan_test = rec.statistical_test_plan.get("test_name", "")
        if plan_test and plan_test.upper() != statistical_test_name.upper():
            blocking_reasons.append(
                f"Statistical test '{statistical_test_name}' differs from preregistered test '{plan_test}'."
            )

        if not multiple_testing_accounted:
            blocking_reasons.append("Multiple testing corrections not accounted for.")

        if dataset_provenance_status not in ("TRUSTED_PROVENANCE_VERIFIED", "VERIFIED_TRUSTED_PROVENANCE"):
            blocking_reasons.append(
                f"Dataset provenance status '{dataset_provenance_status}' is not verified."
            )

        if reproducibility_status not in (
            "REPEATABILITY_VERIFIED",
            "INDEPENDENT_IMPLEMENTATION_REPRODUCED",
            "INDEPENDENT_DATASET_REPLICATED",
        ):
            blocking_reasons.append(f"Reproducibility status '{reproducibility_status}' is not verified.")

        if not has_uncertainty_measures:
            blocking_reasons.append("Required statistical uncertainty measures (e.g. confidence intervals) are absent.")

        is_eligible = len(blocking_reasons) == 0
        gate_status = "CONFIRMATORY_ELIGIBLE" if is_eligible else "CONFIRMATORY_BLOCKED"
        return is_eligible, gate_status, blocking_reasons

    def list_hypotheses(self) -> List[ScientificHypothesisRecord]:
        return list(self._hypotheses.values())

    def get_hypothesis(self, hypothesis_id: str) -> Optional[ScientificHypothesisRecord]:
        return self._hypotheses.get(hypothesis_id)
