"""Unit tests for Pydantic model serialization/deserialization.

pytest markers: unit
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from dprk_er.types.models import (
    CandidateCluster,
    CandidatePair,
    Document,
    ManifestRow,
    Mention,
    ReviewDecision,
    TextChunk,
)


@pytest.mark.unit
class TestDocument:
    def test_create_with_defaults(self) -> None:
        doc = Document(
            title="DPRK Report 2024",
            report_date=date(2024, 3, 7),
            report_type="final",
            source_url="https://example.com/report.pdf",
            checksum="abc123",
        )
        assert doc.doc_id  # auto-generated
        assert isinstance(doc.ingested_at, datetime)
        assert doc.page_count == 0

    def test_roundtrip_json(self) -> None:
        doc = Document(
            doc_id="S-2024-171",
            title="DPRK Final Report",
            report_date=date(2024, 3, 7),
            report_type="final",
            source_url="https://example.com/",
            checksum="deadbeef",
            page_count=42,
        )
        json_str = doc.model_dump_json()
        restored = Document.model_validate_json(json_str)
        assert restored.doc_id == doc.doc_id
        assert restored.page_count == 42

    def test_doc_id_is_string(self) -> None:
        doc = Document(
            title="Test",
            report_date=date(2024, 1, 1),
            report_type="final",
            source_url="https://example.com/",
            checksum="x",
        )
        assert isinstance(doc.doc_id, str)


@pytest.mark.unit
class TestMention:
    def test_create_with_defaults(self) -> None:
        m = Mention(
            doc_id="S-2024-171",
            page=5,
            surface_form="Korea Mining Development Corporation",
            normalized_form="Korea Mining Development Corporation",
            entity_type="ORG",
        )
        assert m.mention_id
        assert m.embedding is None
        assert m.model_name == ""

    def test_roundtrip_json(self) -> None:
        m = Mention(
            doc_id="S-2024-171",
            page=3,
            surface_form="Kim Chol Sam",
            normalized_form="Kim Chol Sam",
            entity_type="PERSON",
            context_left="representative",
            context_right="based in Dalian",
            embedding=[0.1, 0.2, 0.3],
            model_name="all-MiniLM-L6-v2",
        )
        data = json.loads(m.model_dump_json())
        restored = Mention.model_validate(data)
        assert restored.mention_id == m.mention_id
        assert restored.embedding == [0.1, 0.2, 0.3]

    def test_entity_types_accepted(self) -> None:
        for etype in ("ORG", "PERSON", "VESSEL", "LOCATION"):
            m = Mention(
                doc_id="d1",
                page=1,
                surface_form="X",
                normalized_form="X",
                entity_type=etype,
            )
            assert m.entity_type == etype


@pytest.mark.unit
class TestTextChunk:
    def test_create(self) -> None:
        chunk = TextChunk(doc_id="S-2024-171", page=1, text="Hello DPRK.")
        assert chunk.chunk_id
        assert chunk.page == 1

    def test_roundtrip(self) -> None:
        chunk = TextChunk(doc_id="test", page=2, text="Some text here.")
        restored = TextChunk.model_validate(chunk.model_dump())
        assert restored.chunk_id == chunk.chunk_id
        assert restored.text == chunk.text


@pytest.mark.unit
class TestCandidatePair:
    def test_defaults(self) -> None:
        pair = CandidatePair(
            mention_id_a="aaa",
            mention_id_b="bbb",
            score=0.85,
        )
        assert pair.candidate_id
        assert pair.status == "pending"
        assert pair.reasons == []

    def test_roundtrip(self) -> None:
        pair = CandidatePair(
            mention_id_a="aaa",
            mention_id_b="bbb",
            score=0.92,
            reasons=["cosine_sim=0.9200", "exact_normalized_match"],
        )
        data = pair.model_dump()
        restored = CandidatePair.model_validate(data)
        assert restored.reasons == ["cosine_sim=0.9200", "exact_normalized_match"]


@pytest.mark.unit
class TestCandidateCluster:
    def test_defaults(self) -> None:
        cluster = CandidateCluster()
        assert cluster.cluster_id
        assert cluster.member_mentions == []
        assert cluster.cluster_score == 0.0
        assert cluster.status == "pending"

    def test_with_members(self) -> None:
        cluster = CandidateCluster(
            member_mentions=["m1", "m2", "m3"],
            cluster_score=0.88,
        )
        assert len(cluster.member_mentions) == 3


@pytest.mark.unit
class TestReviewDecision:
    def test_create(self) -> None:
        d = ReviewDecision(
            candidate_id="ccc",
            reviewer="analyst-001",
            decision="approved",
            notes="Confirmed alias via source document cross-reference.",
        )
        assert d.decision_id
        assert d.decision == "approved"

    def test_roundtrip(self) -> None:
        d = ReviewDecision(
            candidate_id="cand-1",
            reviewer="analyst-001",
            decision="rejected",
            notes="Different entities.",
            model_version="all-MiniLM-L6-v2@2.7.0",
        )
        data = d.model_dump()
        restored = ReviewDecision.model_validate(data)
        assert restored.decision_id == d.decision_id
        assert restored.model_version == d.model_version


@pytest.mark.unit
class TestManifestRow:
    def test_defaults(self) -> None:
        row = ManifestRow(
            doc_id="S-2024-171",
            title="Test",
            report_type="final",
            report_date=date(2024, 3, 7),
            source_url="https://example.com/",
        )
        assert row.status == "pending"
        assert row.checksum == ""
        assert row.local_path == ""

    def test_roundtrip(self) -> None:
        row = ManifestRow(
            doc_id="S-2024-171",
            title="Report",
            report_type="midterm",
            report_date=date(2022, 9, 7),
            source_url="https://example.com/r.pdf",
            checksum="abc",
            status="fetched",
        )
        data = row.model_dump()
        restored = ManifestRow.model_validate(data)
        assert restored.status == "fetched"
        assert restored.checksum == "abc"
