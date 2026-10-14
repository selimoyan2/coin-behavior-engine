"""Purged and embargoed walk-forward time-series splitter.

Eliminates lookahead and outcome leakage in financial time-series validation
by purging overlapping outcome windows and applying an embargo buffer
following the principles of Advances in Financial Machine Learning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Sequence


@dataclass(frozen=True)
class PurgedFold:
    """A single walk-forward train/validation split with purging metrics."""

    fold_index: int
    train_indices: list[int]
    val_indices: list[int]
    purged_indices: list[int]
    embargo_indices: list[int]
    train_start_idx: int
    train_end_idx: int
    val_start_idx: int
    val_end_idx: int

    @property
    def train_count(self) -> int:
        return len(self.train_indices)

    @property
    def val_count(self) -> int:
        return len(self.val_indices)

    @property
    def purged_count(self) -> int:
        return len(self.purged_indices)

    @property
    def embargo_count(self) -> int:
        return len(self.embargo_indices)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fold_index": self.fold_index,
            "train_count": self.train_count,
            "val_count": self.val_count,
            "purged_count": self.purged_count,
            "embargo_count": self.embargo_count,
            "train_start_idx": self.train_start_idx,
            "train_end_idx": self.train_end_idx,
            "val_start_idx": self.val_start_idx,
            "val_end_idx": self.val_end_idx,
        }


class PurgedEmbargoTimeSeriesSplitter:
    """Walk-forward time-series splitter with label purging and post-evaluation embargo.

    Parameters:
    - n_splits: number of sequential folds.
    - outcome_horizon_bars: number of bars forward that an observation's outcome spans (e.g. 12 for 1h on 5m).
    - embargo_bars: number of bars quarantined after test/val segment to eliminate auto-correlation.
    - min_train_bars: minimum bars required in initial training window.
    """

    def __init__(
        self,
        n_splits: int = 5,
        outcome_horizon_bars: int = 12,
        embargo_bars: int = 6,
        min_train_bars: int = 100,
    ) -> None:
        if n_splits < 1:
            raise ValueError("n_splits must be >= 1")
        if outcome_horizon_bars < 0:
            raise ValueError("outcome_horizon_bars must be >= 0")
        if embargo_bars < 0:
            raise ValueError("embargo_bars must be >= 0")

        self.n_splits = n_splits
        self.outcome_horizon_bars = outcome_horizon_bars
        self.embargo_bars = embargo_bars
        self.min_train_bars = min_train_bars

    def split(self, total_bars: int) -> Iterator[PurgedFold]:
        """Generate purged and embargoed folds across total_bars chronologically."""
        if total_bars < self.min_train_bars + self.n_splits * 10:
            raise ValueError(
                f"Insufficient bars ({total_bars}) for {self.n_splits} splits with "
                f"min_train_bars={self.min_train_bars}"
            )

        # Available space for validation splits
        remaining_bars = total_bars - self.min_train_bars
        val_size = remaining_bars // self.n_splits

        for fold_idx in range(self.n_splits):
            val_start = self.min_train_bars + fold_idx * val_size
            val_end = val_start + val_size if fold_idx < self.n_splits - 1 else total_bars

            # In walk-forward:
            # Raw train window is 0 to val_start.
            # However, observations near val_start whose outcome horizon extends into [val_start, ...]
            # must be PURGED from train to prevent lookahead outcome leakage.
            purge_cutoff = max(0, val_start - self.outcome_horizon_bars)

            train_indices = list(range(0, purge_cutoff))
            purged_indices = list(range(purge_cutoff, val_start))
            val_indices = list(range(val_start, val_end))

            # Embargo indices after val_end
            embargo_end = min(total_bars, val_end + self.embargo_bars)
            embargo_indices = list(range(val_end, embargo_end))

            yield PurgedFold(
                fold_index=fold_idx,
                train_indices=train_indices,
                val_indices=val_indices,
                purged_indices=purged_indices,
                embargo_indices=embargo_indices,
                train_start_idx=0,
                train_end_idx=purge_cutoff,
                val_start_idx=val_start,
                val_end_idx=val_end,
            )
