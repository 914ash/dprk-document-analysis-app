"""LanceDB storage layer.

This is the ONLY module that opens a LanceDB connection or writes to it.
All other modules must call methods on LanceDBStore rather than using lancedb directly.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import lancedb
import pyarrow as pa
import structlog

from dprk_er.types.models import (
    CandidateEvidence,
    CandidateCluster,
    CandidatePair,
    Document,
    Mention,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Arrow schemas
# ---------------------------------------------------------------------------

DOCUMENTS_SCHEMA = pa.schema(
    [
        pa.field("doc_id", pa.string()),
        pa.field("title", pa.string()),
        pa.field("report_date", pa.string()),
        pa.field("report_type", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("checksum", pa.string()),
        pa.field("page_count", pa.int32()),
        pa.field("ingested_at", pa.string()),
    ]
)

MENTIONS_SCHEMA = pa.schema(
    [
        pa.field("mention_id", pa.string()),
        pa.field("doc_id", pa.string()),
        pa.field("page", pa.int32()),
        pa.field("surface_form", pa.string()),
        pa.field("normalized_form", pa.string()),
        pa.field("entity_type", pa.string()),
        pa.field("context_left", pa.string()),
        pa.field("context_right", pa.string()),
        pa.field("chunk_text", pa.string()),
        pa.field("embedding", pa.list_(pa.float32())),
        pa.field("model_name", pa.string()),
        pa.field("extractor_name", pa.string()),
        pa.field("extractor_label", pa.string()),
        pa.field("extractor_confidence", pa.float32()),
        pa.field("created_at", pa.string()),
    ]
)

CANDIDATE_PAIRS_SCHEMA = pa.schema(
    [
        pa.field("candidate_id", pa.string()),
        pa.field("mention_id_a", pa.string()),
        pa.field("mention_id_b", pa.string()),
        pa.field("score", pa.float32()),
        pa.field("reasons", pa.string()),  # JSON list
        pa.field("evidence", pa.string()),  # JSON object
        pa.field("status", pa.string()),
        pa.field("threshold_version", pa.string()),
    ]
)

CANDIDATE_CLUSTERS_SCHEMA = pa.schema(
    [
        pa.field("cluster_id", pa.string()),
        pa.field("member_mentions", pa.string()),  # JSON list
        pa.field("cluster_score", pa.float32()),
        pa.field("status", pa.string()),
    ]
)


class LanceDBStore:
    """Opens / creates a LanceDB database and provides typed upsert/query methods."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        path = db_path or os.environ.get("LANCEDB_PATH", "data/processed/lancedb")
        Path(path).mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(path)
        logger.info("lancedb_connected", path=path)
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Table bootstrap
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        try:
            existing = self._db.list_tables()
        except AttributeError:
            existing = self._db.table_names()
        if "documents" not in existing:
            self._db.create_table("documents", schema=DOCUMENTS_SCHEMA)
        if "mentions" not in existing:
            self._db.create_table("mentions", schema=MENTIONS_SCHEMA)
        if "candidate_pairs" not in existing:
            self._db.create_table("candidate_pairs", schema=CANDIDATE_PAIRS_SCHEMA)
        if "candidate_clusters" not in existing:
            self._db.create_table("candidate_clusters", schema=CANDIDATE_CLUSTERS_SCHEMA)

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def upsert_documents(self, docs: list[Document]) -> None:
        if not docs:
            return
        rows: list[dict[str, Any]] = [
            {
                "doc_id": d.doc_id,
                "title": d.title,
                "report_date": d.report_date.isoformat(),
                "report_type": d.report_type,
                "source_url": d.source_url,
                "checksum": d.checksum,
                "page_count": d.page_count,
                "ingested_at": d.ingested_at.isoformat(),
            }
            for d in docs
        ]
        tbl = self._db.open_table("documents")
        # Delete existing rows for these doc_ids then re-insert (upsert pattern)
        existing_ids = {d["doc_id"] for d in self._table_to_dicts("documents")}
        new_ids = {r["doc_id"] for r in rows}
        ids_to_delete = existing_ids & new_ids
        if ids_to_delete:
            id_list = ", ".join(f"'{i}'" for i in ids_to_delete)
            tbl.delete(f"doc_id IN ({id_list})")
        tbl.add(rows)
        logger.info("documents_upserted", count=len(rows))

    def get_documents(self, doc_id: Optional[str] = None) -> list[Document]:
        rows = self._table_to_dicts("documents")
        if doc_id:
            rows = [r for r in rows if r["doc_id"] == doc_id]
        return [
            Document(
                doc_id=r["doc_id"],
                title=r["title"],
                report_date=r["report_date"],
                report_type=r["report_type"],
                source_url=r["source_url"],
                checksum=r["checksum"],
                page_count=r["page_count"],
                ingested_at=r["ingested_at"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Mentions
    # ------------------------------------------------------------------

    def upsert_mentions(self, mentions: list[Mention]) -> None:
        if not mentions:
            return
        rows: list[dict[str, Any]] = [
            {
                "mention_id": m.mention_id,
                "doc_id": m.doc_id,
                "page": m.page,
                "surface_form": m.surface_form,
                "normalized_form": m.normalized_form,
                "entity_type": m.entity_type,
                "context_left": m.context_left,
                "context_right": m.context_right,
                "chunk_text": m.chunk_text,
                "embedding": m.embedding if m.embedding is not None else [0.0] * 384,
                "model_name": m.model_name,
                "extractor_name": m.extractor_name,
                "extractor_label": m.extractor_label,
                "extractor_confidence": m.extractor_confidence,
                "created_at": m.created_at.isoformat(),
            }
            for m in mentions
        ]
        tbl = self._db.open_table("mentions")
        existing_ids = {r["mention_id"] for r in self._table_to_dicts("mentions")}
        new_ids = {r["mention_id"] for r in rows}
        ids_to_delete = existing_ids & new_ids
        if ids_to_delete:
            id_list = ", ".join(f"'{i}'" for i in ids_to_delete)
            tbl.delete(f"mention_id IN ({id_list})")
        tbl.add(rows)
        logger.info("mentions_upserted", count=len(rows))

    def get_mentions(
        self,
        doc_id: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> list[Mention]:
        rows = self._table_to_dicts("mentions")
        if doc_id:
            rows = [r for r in rows if r["doc_id"] == doc_id]
        if entity_type:
            rows = [r for r in rows if r["entity_type"] == entity_type]
        return [self._row_to_mention(r) for r in rows]

    def search_mentions(self, query_vector: list[float], limit: int = 10) -> list[Mention]:
        tbl = self._db.open_table("mentions")
        results = tbl.search(query_vector).limit(limit).to_list()
        return [self._row_to_mention(r) for r in results]

    def _row_to_mention(self, r: dict[str, Any]) -> Mention:
        emb = r.get("embedding")
        return Mention(
            mention_id=r["mention_id"],
            doc_id=r["doc_id"],
            page=r["page"],
            surface_form=r["surface_form"],
            normalized_form=r["normalized_form"],
            entity_type=r["entity_type"],
            context_left=r.get("context_left", ""),
            context_right=r.get("context_right", ""),
            chunk_text=r.get("chunk_text", ""),
            embedding=list(emb) if emb is not None else None,
            model_name=r.get("model_name", ""),
            extractor_name=r.get("extractor_name", ""),
            extractor_label=r.get("extractor_label", ""),
            extractor_confidence=float(r.get("extractor_confidence", 0.0) or 0.0),
            created_at=r.get("created_at", ""),
        )

    # ------------------------------------------------------------------
    # Candidate pairs
    # ------------------------------------------------------------------

    def upsert_candidates(self, pairs: list[CandidatePair]) -> None:
        if not pairs:
            return
        rows: list[dict[str, Any]] = [
            {
                "candidate_id": p.candidate_id,
                "mention_id_a": p.mention_id_a,
                "mention_id_b": p.mention_id_b,
                "score": p.score,
                "reasons": json.dumps(p.reasons),
                "evidence": json.dumps(p.evidence.model_dump(mode="json")),
                "status": p.status,
                "threshold_version": p.threshold_version,
            }
            for p in pairs
        ]
        tbl = self._db.open_table("candidate_pairs")
        existing_ids = {r["candidate_id"] for r in self._table_to_dicts("candidate_pairs")}
        new_ids = {r["candidate_id"] for r in rows}
        ids_to_delete = existing_ids & new_ids
        if ids_to_delete:
            id_list = ", ".join(f"'{i}'" for i in ids_to_delete)
            tbl.delete(f"candidate_id IN ({id_list})")
        tbl.add(rows)
        logger.info("candidates_upserted", count=len(rows))

    def get_candidates(self, status: Optional[str] = None) -> list[CandidatePair]:
        rows = self._table_to_dicts("candidate_pairs")
        if status:
            rows = [r for r in rows if r["status"] == status]
        return [
            CandidatePair(
                candidate_id=r["candidate_id"],
                mention_id_a=r["mention_id_a"],
                mention_id_b=r["mention_id_b"],
                score=float(r["score"]),
                reasons=json.loads(r.get("reasons", "[]")),
                evidence=CandidateEvidence(**json.loads(r.get("evidence", "{}") or "{}")),
                status=r["status"],
                threshold_version=r.get("threshold_version", "legacy-v1"),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Candidate clusters
    # ------------------------------------------------------------------

    def upsert_clusters(self, clusters: list[CandidateCluster]) -> None:
        if not clusters:
            return
        rows: list[dict[str, Any]] = [
            {
                "cluster_id": c.cluster_id,
                "member_mentions": json.dumps(c.member_mentions),
                "cluster_score": c.cluster_score,
                "status": c.status,
            }
            for c in clusters
        ]
        tbl = self._db.open_table("candidate_clusters")
        existing_ids = {r["cluster_id"] for r in self._table_to_dicts("candidate_clusters")}
        new_ids = {r["cluster_id"] for r in rows}
        ids_to_delete = existing_ids & new_ids
        if ids_to_delete:
            id_list = ", ".join(f"'{i}'" for i in ids_to_delete)
            tbl.delete(f"cluster_id IN ({id_list})")
        tbl.add(rows)
        logger.info("clusters_upserted", count=len(rows))

    def get_clusters(self, status: Optional[str] = None) -> list[CandidateCluster]:
        rows = self._table_to_dicts("candidate_clusters")
        if status:
            rows = [r for r in rows if r["status"] == status]
        return [
            CandidateCluster(
                cluster_id=r["cluster_id"],
                member_mentions=json.loads(r.get("member_mentions", "[]")),
                cluster_score=float(r["cluster_score"]),
                status=r["status"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _table_to_dicts(self, table_name: str) -> list[dict[str, Any]]:
        """Return all rows from a table as a list of dicts."""
        try:
            tbl = self._db.open_table(table_name)
            return tbl.to_pandas().to_dict(orient="records")
        except Exception:
            return []
