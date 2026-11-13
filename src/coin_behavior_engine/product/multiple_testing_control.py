"""Statistical False Discovery & Multiple Testing Control (Module 28.6).

Accounts for multi-hypothesis testing in historical market research:
- Formal testing family registration (family_id, research_id, hypotheses, test_count).
- Mathematically exact corrections:
    Bonferroni (FWER control)
    Holm (Step-down Bonferroni)
    Benjamini-Hochberg (FDR control under independence/positive dependence)
    Benjamini-Yekutieli (FDR control under arbitrary dependence)
- Sensitivity analysis across correction methods.
- Explicit disclosures: Low adjusted p-value is not economic utility or live trading eligibility.
- Durable JSON persistence.
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

import numpy as np

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FAMILY_PERSISTENCE = REPO_ROOT / "data" / "research_lab" / "testing_families.json"

SUPPORTED_CORRECTION_METHODS: Set[str] = {
    "BONFERRONI",
    "HOLM",
    "BENJAMINI_HOCHBERG",
    "BENJAMINI_YEKUTIELI",
}


@dataclass
class MultipleTestingFamily:
    """Registered testing family binding related statistical hypothesis evaluations."""
    testing_family_id: str
    research_id: str
    family_definition: str
    hypothesis_ids: List[str]
    test_count: int
    family_registration_timestamp: str
    correction_method: str = "BENJAMINI_HOCHBERG"
    correction_parameters: Dict[str, Any] = field(default_factory=lambda: {"alpha": 0.05})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FalseDiscoveryResult:
    """Corrected p-value and false discovery control status for a single test."""
    hypothesis_id: str
    raw_p_value: float
    adjusted_p_value: float
    correction_method: str
    testing_family_size: int
    significance_threshold: float
    is_significant_after_correction: bool
    false_discovery_control_status: str  # CONTROLLED_SIGNIFICANT, CONTROLLED_INSIGNIFICANT, UNCORRECTED
    selection_bias_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultipleTestingControlEngine:
    """Engine managing statistical testing families and rigorous multiple testing corrections."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self.persistence_path = persistence_path or DEFAULT_FAMILY_PERSISTENCE
        self._families: Dict[str, MultipleTestingFamily] = {}
        self._load_from_storage()
        if not self._families:
            self._seed_canonical_families()

    def _load_from_storage(self) -> None:
        """Load registered families from disk."""
        if not self.persistence_path.exists():
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw.get("families", []):
                rec = MultipleTestingFamily(**item)
                self._families[rec.testing_family_id] = rec
        except Exception as e:
            logger.error(f"Error loading testing families: {e}")

    def save_to_storage(self) -> None:
        """Atomically persist testing families."""
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.persistence_path.with_suffix(".tmp")
        payload = {
            "schema_version": "CBE-TESTING-FAMILIES-V28",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "families": [f.to_dict() for f in self._families.values()],
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(self.persistence_path)

    def _seed_canonical_families(self) -> None:
        """Seed canonical multiple testing families."""
        f1 = MultipleTestingFamily(
            testing_family_id="FAM-VOL-DYNAMICS-01",
            research_id="RES-STAT-02",
            family_definition="Family of BTC return volatility clustering and ARCH lag specifications.",
            hypothesis_ids=["HYP-VOL-PERSIST-001", "HYP-VOL-LAG2-001B", "HYP-VOL-LAG5-001C", "HYP-VOL-15M-001D"],
            test_count=4,
            family_registration_timestamp="2024-01-01T00:00:00Z",
            correction_method="HOLM",
            correction_parameters={"alpha": 0.01},
        )
        self._families[f1.testing_family_id] = f1

        f2 = MultipleTestingFamily(
            testing_family_id="FAM-REGIME-DIST-01",
            research_id="RES-GEN-05",
            family_definition="Family of cross-regime Kolmogorov-Smirnov distribution comparisons.",
            hypothesis_ids=["HYP-REG-SHIFT-002", "HYP-REG-VOL-HIGH-002B", "HYP-REG-VOL-LOW-002C"],
            test_count=3,
            family_registration_timestamp="2024-01-01T00:00:00Z",
            correction_method="BENJAMINI_HOCHBERG",
            correction_parameters={"alpha": 0.05},
        )
        self._families[f2.testing_family_id] = f2

        f3 = MultipleTestingFamily(
            testing_family_id="FAM-ANALOG-01",
            research_id="RES-HIST-01",
            family_definition="Family of retrospective analog pattern similarity evaluations.",
            hypothesis_ids=["HYP-RETRO-ANALOG-003", "HYP-RETRO-COSINE-003B"],
            test_count=2,
            family_registration_timestamp="2024-01-01T00:00:00Z",
            correction_method="BONFERRONI",
            correction_parameters={"alpha": 0.05},
        )
        self._families[f3.testing_family_id] = f3

        self.save_to_storage()

    @classmethod
    def bonferroni_correction(cls, p_values: List[float]) -> List[float]:
        """Mathematically exact Bonferroni adjustment: p_adj = min(1.0, m * p)."""
        m = len(p_values)
        if m == 0:
            return []
        return [min(1.0, float(p) * m) for p in p_values]

    @classmethod
    def holm_bonferroni_correction(cls, p_values: List[float]) -> List[float]:
        """Mathematically exact step-down Holm-Bonferroni correction:

        Sort p-values: p_(1) <= ... <= p_(m)
        p_adj_(i) = min(1.0, max_{k <= i} (m - k + 1) * p_(k))
        """
        m = len(p_values)
        if m == 0:
            return []
        if m == 1:
            return [min(1.0, float(p_values[0]))]

        # Keep original order indices
        indexed_p = sorted(enumerate(p_values), key=lambda x: x[1])
        adj_sorted: List[float] = [0.0] * m

        running_max = 0.0
        for rank, (orig_idx, p_val) in enumerate(indexed_p):
            k = rank + 1
            multiplier = m - k + 1
            cand = multiplier * p_val
            running_max = max(running_max, cand)
            adj_sorted[rank] = min(1.0, running_max)

        # Restore original order
        result = [0.0] * m
        for rank, (orig_idx, _) in enumerate(indexed_p):
            result[orig_idx] = adj_sorted[rank]
        return result

    @classmethod
    def benjamini_hochberg_correction(cls, p_values: List[float]) -> List[float]:
        """Mathematically exact Benjamini-Hochberg FDR correction:

        Sort p-values: p_(1) <= ... <= p_(m)
        p_adj_(i) = min(1.0, min_{k >= i} (m / k) * p_(k))
        """
        m = len(p_values)
        if m == 0:
            return []
        if m == 1:
            return [min(1.0, float(p_values[0]))]

        indexed_p = sorted(enumerate(p_values), key=lambda x: x[1])
        raw_sorted = [x[1] for x in indexed_p]

        # Step down from the largest p-value
        adj_sorted = [0.0] * m
        adj_sorted[-1] = min(1.0, raw_sorted[-1])
        for i in range(m - 2, -1, -1):
            k = i + 1
            cand = (m / k) * raw_sorted[i]
            adj_sorted[i] = min(1.0, min(cand, adj_sorted[i + 1]))

        # Restore original order
        result = [0.0] * m
        for rank, (orig_idx, _) in enumerate(indexed_p):
            result[orig_idx] = adj_sorted[rank]
        return result

    @classmethod
    def benjamini_yekutieli_correction(cls, p_values: List[float]) -> List[float]:
        """Mathematically exact Benjamini-Yekutieli FDR correction under arbitrary dependence:

        c(m) = sum_{j=1}^m 1/j
        p_adj_(i) = min(1.0, min_{k >= i} (m * c(m) / k) * p_(k))
        """
        m = len(p_values)
        if m == 0:
            return []
        harmonic_sum = sum(1.0 / j for j in range(1, m + 1))
        # Scale p-values by harmonic sum then apply BH
        scaled_p = [min(1.0, p * harmonic_sum) for p in p_values]
        return cls.benjamini_hochberg_correction(scaled_p)

    def apply_family_correction(
        self,
        testing_family_id: str,
        hypothesis_p_values: Dict[str, float],
        method: Optional[str] = None,
        alpha: float = 0.05,
    ) -> List[FalseDiscoveryResult]:
        """Apply multiple testing correction to a dict of {hypothesis_id: raw_p_value}

        belonging to the registered family.
        """
        fam = self._families.get(testing_family_id)
        if not fam:
            raise KeyError(f"Testing family '{testing_family_id}' is not registered.")

        correction_method = (method or fam.correction_method).upper()
        if correction_method not in SUPPORTED_CORRECTION_METHODS:
            raise ValueError(f"Unsupported correction method: {correction_method}")

        hyp_ids = list(hypothesis_p_values.keys())
        raw_ps = [hypothesis_p_values[h] for h in hyp_ids]
        m = len(raw_ps)

        if correction_method == "BONFERRONI":
            adj_ps = self.bonferroni_correction(raw_ps)
        elif correction_method == "HOLM":
            adj_ps = self.holm_bonferroni_correction(raw_ps)
        elif correction_method == "BENJAMINI_HOCHBERG":
            adj_ps = self.benjamini_hochberg_correction(raw_ps)
        elif correction_method == "BENJAMINI_YEKUTIELI":
            adj_ps = self.benjamini_yekutieli_correction(raw_ps)
        else:
            adj_ps = raw_ps

        results: List[FalseDiscoveryResult] = []
        for h_id, raw_p, adj_p in zip(hyp_ids, raw_ps, adj_ps):
            is_sig = adj_p <= alpha
            status = "CONTROLLED_SIGNIFICANT" if is_sig else "CONTROLLED_INSIGNIFICANT"
            bias_warn = None
            if m < fam.test_count:
                bias_warn = f"Subset of tests evaluated ({m} of registered {fam.test_count}); potential reporting selection."

            results.append(
                FalseDiscoveryResult(
                    hypothesis_id=h_id,
                    raw_p_value=raw_p,
                    adjusted_p_value=adj_p,
                    correction_method=correction_method,
                    testing_family_size=m,
                    significance_threshold=alpha,
                    is_significant_after_correction=is_sig,
                    false_discovery_control_status=status,
                    selection_bias_warning=bias_warn,
                )
            )

        return results

    @classmethod
    def sensitivity_analysis(
        cls, hypothesis_p_values: Dict[str, float], alpha: float = 0.05
    ) -> Dict[str, Any]:
        """Perform sensitivity analysis comparing conclusions across all correction methods."""
        hyp_ids = list(hypothesis_p_values.keys())
        raw_ps = [hypothesis_p_values[h] for h in hyp_ids]

        bonf = cls.bonferroni_correction(raw_ps)
        holm = cls.holm_bonferroni_correction(raw_ps)
        bh = cls.benjamini_hochberg_correction(raw_ps)
        by = cls.benjamini_yekutieli_correction(raw_ps)

        comparison_table = []
        for i, h_id in enumerate(hyp_ids):
            comparison_table.append({
                "hypothesis_id": h_id,
                "raw_p": raw_ps[i],
                "bonferroni_p": bonf[i],
                "bonferroni_sig": bonf[i] <= alpha,
                "holm_p": holm[i],
                "holm_sig": holm[i] <= alpha,
                "benjamini_hochberg_p": bh[i],
                "benjamini_hochberg_sig": bh[i] <= alpha,
                "benjamini_yekutieli_p": by[i],
                "benjamini_yekutieli_sig": by[i] <= alpha,
            })

        return {
            "alpha": alpha,
            "test_count": len(hyp_ids),
            "comparison": comparison_table,
            "conclusion_stability": (
                "STABLE"
                if all(c["bonferroni_sig"] == c["benjamini_hochberg_sig"] for c in comparison_table)
                else "SENSITIVE_TO_CORRECTION_METHOD"
            ),
        }

    def list_families(self) -> List[MultipleTestingFamily]:
        return list(self._families.values())

    def get_family(self, family_id: str) -> Optional[MultipleTestingFamily]:
        return self._families.get(family_id)

    @classmethod
    def apply_fdr_correction(
        cls,
        p_values: List[float],
        alpha: float = 0.05,
        method: str = "BENJAMINI_HOCHBERG",
    ) -> Any:
        """Apply FDR or FWER correction directly to a list of p-values."""
        if method == "BENJAMINI_HOCHBERG":
            adj = cls.benjamini_hochberg_correction(p_values)
        elif method == "BONFERRONI":
            adj = cls.bonferroni_correction(p_values)
        elif method == "HOLM":
            adj = cls.holm_bonferroni_correction(p_values)
        elif method == "BENJAMINI_YEKUTIELI":
            adj = cls.benjamini_yekutieli_correction(p_values)
        else:
            raise ValueError(f"Unsupported method: {method}")

        rejected = [bool(p <= alpha) for p in adj]

        from dataclasses import make_dataclass
        Res = make_dataclass("FDRCorrectionResult", [
            ("p_values", list),
            ("adjusted_p_values", list),
            ("rejected", list),
            ("alpha", float),
            ("method", str),
        ])
        return Res(
            p_values=list(p_values),
            adjusted_p_values=adj,
            rejected=rejected,
            alpha=float(alpha),
            method=str(method),
        )
