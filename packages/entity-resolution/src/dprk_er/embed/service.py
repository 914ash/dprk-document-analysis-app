"""Embed service – embeds Mention records using sentence-transformers.

Architecture: may import from dprk_er.types only.
"""

from __future__ import annotations

import os
from typing import Optional

import structlog

from dprk_er.types.models import Mention

logger = structlog.get_logger(__name__)

_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_BATCH_SIZE = 64


class EmbedService:
    """Embeds entity mentions using a sentence-transformers model."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or os.environ.get("EMBEDDING_MODEL", _DEFAULT_MODEL)
        self._model: Optional[object] = None  # Lazy-loaded

    def _get_model(self) -> object:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

                self._model = SentenceTransformer(self.model_name)
                logger.info("embedding_model_loaded", model=self.model_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not load sentence-transformers model '{self.model_name}': {exc}"
                ) from exc
        return self._model

    # ------------------------------------------------------------------
    # Core embedding
    # ------------------------------------------------------------------

    def _build_input_text(self, mention: Mention) -> str:
        """Build the embedding input from surface form + context."""
        parts = [mention.surface_form]
        if mention.context_left:
            parts = [mention.context_left] + parts
        if mention.context_right:
            parts = parts + [mention.context_right]
        return " ".join(parts)

    def embed_mention(self, mention: Mention) -> Mention:
        """Embed a single mention. Returns a new Mention with embedding filled."""
        model = self._get_model()
        text = self._build_input_text(mention)
        vector = model.encode(text, convert_to_numpy=True).tolist()  # type: ignore[union-attr]
        return mention.model_copy(
            update={
                "embedding": vector,
                "model_name": self.model_name,
            }
        )

    def embed_batch(self, mentions: list[Mention], batch_size: int = _DEFAULT_BATCH_SIZE) -> list[Mention]:
        """Embed a batch of mentions efficiently.

        Sends texts to the model in batches to minimise overhead.
        Returns a new list of Mention objects with embeddings filled.
        """
        if not mentions:
            return []
        model = self._get_model()
        texts = [self._build_input_text(m) for m in mentions]

        # Encode all in one call (sentence-transformers handles internal batching)
        import numpy as np  # type: ignore[import-untyped]
        vectors = model.encode(  # type: ignore[union-attr]
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        embedded: list[Mention] = []
        for mention, vec in zip(mentions, vectors):
            embedded.append(
                mention.model_copy(
                    update={
                        "embedding": vec.tolist(),
                        "model_name": self.model_name,
                    }
                )
            )
        logger.info("mentions_embedded", count=len(embedded), model=self.model_name)
        return embedded
