"""Review service – manages the analyst review queue for alias candidate pairs.

Architecture: may import from dprk_er.types and dprk_er.storage.
All persistence is delegated to Parquet (decisions) or LanceDB (candidates).
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import structlog

from dprk_er.types.models import CandidatePair, ReviewDecision

logger = structlog.get_logger(__name__)

_DEFAULT_DECISIONS_PATH = "data/review/decisions.parquet"


class ReviewService:
    """Manages the analyst review queue and decision persistence."""

    def __init__(
        self,
        decisions_path: str = _DEFAULT_DECISIONS_PATH,
        store: object = None,  # Optional LanceDBStore injection
    ) -> None:
        self.decisions_path = Path(decisions_path)
        self.decisions_path.parent.mkdir(parents=True, exist_ok=True)
        self._store = store  # LanceDBStore – injected to avoid circular deps

    # ------------------------------------------------------------------
    # Candidate queue
    # ------------------------------------------------------------------

    def get_pending_candidates(self) -> list[CandidatePair]:
        """Return all candidate pairs with status='pending' from LanceDB."""
        if self._store is None:
            logger.warning("no_store_configured", method="get_pending_candidates")
            return []
        return self._store.get_candidates(status="pending")  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Decision persistence
    # ------------------------------------------------------------------

    def submit_decision(self, decision: ReviewDecision) -> None:
        """Persist a single analyst decision to Parquet.

        Appends to the existing file (or creates it if absent).
        Also updates the corresponding candidate pair status in LanceDB.
        """
        existing = self.load_decisions()
        # Replace existing decision for same candidate_id (upsert by decision_id)
        existing = [d for d in existing if d.decision_id != decision.decision_id]
        existing.append(decision)
        self.save_decisions(existing)

        # Update candidate status in LanceDB if store is available
        if self._store is not None:
            candidates = self._store.get_candidates()  # type: ignore[union-attr]
            updated: list[CandidatePair] = []
            for c in candidates:
                if c.candidate_id == decision.candidate_id:
                    c = c.model_copy(update={"status": decision.decision})
                    updated.append(c)
            if updated:
                self._store.upsert_candidates(updated)  # type: ignore[union-attr]

        logger.info(
            "decision_submitted",
            decision_id=decision.decision_id,
            candidate_id=decision.candidate_id,
            decision=decision.decision,
        )

    def load_decisions(self) -> list[ReviewDecision]:
        """Load all decisions from Parquet. Returns empty list if file absent."""
        if not self.decisions_path.exists():
            return []
        try:
            df = pd.read_parquet(str(self.decisions_path))
            decisions: list[ReviewDecision] = []
            for _, row in df.iterrows():
                decisions.append(ReviewDecision(**row.to_dict()))
            return decisions
        except Exception as exc:
            logger.error("decisions_load_failed", error=str(exc))
            return []

    def save_decisions(self, decisions: list[ReviewDecision]) -> None:
        """Write all decisions to data/review/decisions.parquet."""
        records = [d.model_dump(mode="json") for d in decisions]
        df = pd.DataFrame(records)
        df.to_parquet(str(self.decisions_path), index=False)
        logger.info("decisions_saved", count=len(decisions), path=str(self.decisions_path))
