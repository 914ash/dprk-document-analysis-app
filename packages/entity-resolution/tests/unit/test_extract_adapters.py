"""Unit tests for extractor adapter selection and metadata propagation."""

from __future__ import annotations

import pytest

from dprk_er.extract.service import ExtractService, ExtractedEntity, build_extractor_adapter
from dprk_er.types.models import TextChunk


class StubAdapter:
    """Deterministic test adapter."""

    name = "stub-adapter"

    def extract(self, text: str, labels: list[str]) -> list[ExtractedEntity]:
        start = text.index("Korea Mining Development Corp")
        end = start + len("Korea Mining Development Corp")
        return [
            ExtractedEntity(
                text="Korea Mining Development Corp",
                label="ORG",
                score=0.91,
                start_char=start,
                end_char=end,
            )
        ]


@pytest.mark.unit
def test_build_extractor_adapter_supports_gliner() -> None:
    adapter = build_extractor_adapter("gliner")
    assert adapter.name == "gliner"


@pytest.mark.unit
def test_build_extractor_adapter_supports_huggingface() -> None:
    adapter = build_extractor_adapter("huggingface")
    assert adapter.name == "huggingface-token-classification"


@pytest.mark.unit
def test_extract_mentions_propagates_adapter_metadata() -> None:
    svc = ExtractService(extractor=StubAdapter())
    chunk = TextChunk(
        doc_id="TEST-001",
        page=1,
        text="The investigation identified Korea Mining Development Corp in the transfer chain.",
    )

    mentions = svc.extract_mentions([chunk], "TEST-001")

    assert len(mentions) == 1
    assert mentions[0].extractor_name == "stub-adapter"
    assert mentions[0].extractor_label == "ORG"
    assert mentions[0].extractor_confidence == pytest.approx(0.91)
