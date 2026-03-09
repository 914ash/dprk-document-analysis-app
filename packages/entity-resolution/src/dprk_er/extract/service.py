"""Extract service with pluggable entity-extractor adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog

from dprk_er.types.models import Mention, TextChunk

logger = structlog.get_logger(__name__)

_CONTEXT_WINDOW = 50
_DEFAULT_GLiner_MODEL = "urchade/gliner_medium-v2.1"
_DEFAULT_HF_MODEL = "dslim/bert-base-NER"
_ACCEPTED_TYPES = {"ORG", "PERSON", "VESSEL", "LOCATION"}

_TYPE_MAP: dict[str, str] = {
    "ORG": "ORG",
    "ORGANIZATION": "ORG",
    "PERSON": "PERSON",
    "PER": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "LOCATION": "LOCATION",
    "FAC": "LOCATION",
    "SHIP": "VESSEL",
    "VESSEL": "VESSEL",
}


@dataclass(frozen=True)
class ExtractedEntity:
    """Normalized adapter output for a single entity span."""

    text: str
    label: str
    score: float
    start_char: int
    end_char: int


class EntityExtractorAdapter(Protocol):
    """Protocol implemented by extractor backends."""

    name: str

    def extract(self, text: str, labels: list[str]) -> list[ExtractedEntity]:
        """Return normalized entity spans for *text*."""


class GLiNERAdapter:
    """GLiNER-backed zero-shot extractor."""

    name = "gliner"

    def __init__(self, model_name: str = _DEFAULT_GLiner_MODEL) -> None:
        self.model_name = model_name
        self._model: object | None = None

    def _get_model(self) -> object:
        if self._model is None:
            try:
                from gliner import GLiNER  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "GLiNER is not installed. Install the 'gliner' dependency "
                    "or use ExtractService(extractor_kind='huggingface')."
                ) from exc
            self._model = GLiNER.from_pretrained(self.model_name)
            logger.info("extractor_model_loaded", extractor=self.name, model=self.model_name)
        return self._model

    def extract(self, text: str, labels: list[str]) -> list[ExtractedEntity]:
        model = self._get_model()
        raw_entities = model.predict_entities(text, labels)  # type: ignore[operator]
        entities: list[ExtractedEntity] = []
        for entity in raw_entities:
            entities.append(
                ExtractedEntity(
                    text=str(entity.get("text", "")),
                    label=str(entity.get("label", "")),
                    score=float(entity.get("score", 0.0) or 0.0),
                    start_char=int(entity.get("start", 0) or 0),
                    end_char=int(entity.get("end", 0) or 0),
                )
            )
        return entities


class HuggingFaceTokenClassificationAdapter:
    """Transformers token-classification fallback extractor."""

    name = "huggingface-token-classification"

    def __init__(self, model_name: str = _DEFAULT_HF_MODEL) -> None:
        self.model_name = model_name
        self._pipeline: object | None = None

    def _get_pipeline(self) -> object:
        if self._pipeline is None:
            try:
                from transformers import pipeline  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "transformers is not installed. Install the 'transformers' dependency "
                    "or use ExtractService(extractor_kind='gliner')."
                ) from exc
            self._pipeline = pipeline(
                "token-classification",
                model=self.model_name,
                aggregation_strategy="simple",
            )
            logger.info("extractor_model_loaded", extractor=self.name, model=self.model_name)
        return self._pipeline

    def extract(self, text: str, labels: list[str]) -> list[ExtractedEntity]:
        entity_pipeline = self._get_pipeline()
        raw_entities = entity_pipeline(text)  # type: ignore[operator]
        accepted = {label.upper() for label in labels}
        entities: list[ExtractedEntity] = []
        for entity in raw_entities:
            label = str(entity.get("entity_group", entity.get("entity", ""))).upper()
            mapped = _TYPE_MAP.get(label, label)
            if mapped not in accepted:
                continue
            entities.append(
                ExtractedEntity(
                    text=str(entity.get("word", "")),
                    label=mapped,
                    score=float(entity.get("score", 0.0) or 0.0),
                    start_char=int(entity.get("start", 0) or 0),
                    end_char=int(entity.get("end", 0) or 0),
                )
            )
        return entities


def build_extractor_adapter(
    extractor_kind: str | None = None,
    model_name: str | None = None,
) -> EntityExtractorAdapter:
    """Create an extractor adapter by name."""

    kind = (extractor_kind or "gliner").strip().lower()
    if kind == "gliner":
        return GLiNERAdapter(model_name=model_name or _DEFAULT_GLiner_MODEL)
    if kind in {"huggingface", "hf"}:
        return HuggingFaceTokenClassificationAdapter(
            model_name=model_name or _DEFAULT_HF_MODEL
        )
    raise ValueError(f"Unsupported extractor_kind '{extractor_kind}'")


class ExtractService:
    """Extract entity mentions from text chunks using a pluggable adapter."""

    def __init__(
        self,
        extractor: EntityExtractorAdapter | None = None,
        extractor_kind: str = "gliner",
        model_name: str | None = None,
    ) -> None:
        self.extractor = extractor or build_extractor_adapter(extractor_kind, model_name)

    def extract_mentions(self, chunks: list[TextChunk], doc_id: str) -> list[Mention]:
        mentions: list[Mention] = []

        for chunk in chunks:
            if not chunk.text.strip():
                continue
            try:
                entities = self.extractor.extract(chunk.text, sorted(_ACCEPTED_TYPES))
                for entity in entities:
                    entity_type = self._map_type(entity.label)
                    if entity_type not in _ACCEPTED_TYPES:
                        continue
                    normalized = self._normalize(entity.text, entity_type)
                    if not normalized:
                        continue
                    ctx_left, ctx_right = self._extract_context(
                        chunk.text, entity.start_char, entity.end_char
                    )
                    mentions.append(
                        Mention(
                            doc_id=doc_id,
                            page=chunk.page,
                            surface_form=entity.text,
                            normalized_form=normalized,
                            entity_type=entity_type,
                            context_left=ctx_left,
                            context_right=ctx_right,
                            chunk_text=chunk.text,
                            extractor_name=self.extractor.name,
                            extractor_label=entity.label,
                            extractor_confidence=entity.score,
                        )
                    )
            except (ImportError, OSError):
                raise
            except Exception as exc:
                logger.warning(
                    "chunk_extract_failed",
                    doc_id=doc_id,
                    page=chunk.page,
                    extractor=self.extractor.name,
                    error=str(exc),
                )

        logger.info(
            "mentions_extracted",
            doc_id=doc_id,
            count=len(mentions),
            extractor=self.extractor.name,
        )
        return mentions

    @staticmethod
    def _map_type(extractor_label: str) -> str:
        return _TYPE_MAP.get(extractor_label.upper(), "ORG")

    @staticmethod
    def _normalize(surface: str, entity_type: str) -> str:
        text = " ".join(surface.split())
        if entity_type in ("ORG", "PERSON"):
            text = text.title()
        return text

    @staticmethod
    def _extract_context(full_text: str, start: int, end: int) -> tuple[str, str]:
        left_start = max(0, start - _CONTEXT_WINDOW)
        right_end = min(len(full_text), end + _CONTEXT_WINDOW)
        ctx_left = full_text[left_start:start].replace("\n", " ").strip()
        ctx_right = full_text[end:right_end].replace("\n", " ").strip()
        return ctx_left, ctx_right

    def extract_all(self, chunks: list[TextChunk]) -> list[Mention]:
        doc_chunks: dict[str, list[TextChunk]] = {}
        for chunk in chunks:
            doc_chunks.setdefault(chunk.doc_id, []).append(chunk)

        all_mentions: list[Mention] = []
        for doc_id, doc_chunk_list in doc_chunks.items():
            all_mentions.extend(self.extract_mentions(doc_chunk_list, doc_id))
        return all_mentions
