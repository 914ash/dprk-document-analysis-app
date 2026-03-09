"""Parse service – converts PDF files to structured TextChunk records.

Architecture: may import from dprk_er.types only.
Uses PyMuPDF (fitz) for PDF text extraction.
"""

from __future__ import annotations

from pathlib import Path

import structlog

from dprk_er.types.models import TextChunk

logger = structlog.get_logger(__name__)

_DEFAULT_INTERIM_DIR = "data/interim"


class ParseService:
    """Extracts page-level text from PDF files into TextChunk records."""

    def __init__(self, interim_dir: str = _DEFAULT_INTERIM_DIR) -> None:
        self.interim_dir = Path(interim_dir)
        self.interim_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core extraction
    # ------------------------------------------------------------------

    def parse_pdf(self, local_path: str, doc_id: str) -> list[TextChunk]:
        """Extract page text from a PDF and return one TextChunk per page.

        Raises FileNotFoundError if the PDF does not exist.
        Returns an empty list if no text could be extracted.
        """
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {local_path}")

        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ImportError(
                "PyMuPDF is required for PDF parsing. Install it with: pip install pymupdf"
            ) from exc

        chunks: list[TextChunk] = []
        try:
            doc = fitz.open(str(path))
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                # Normalize whitespace while preserving paragraph breaks
                text = self._normalize_text(text)
                if text:
                    chunk = TextChunk(
                        doc_id=doc_id,
                        page=page_num + 1,  # 1-indexed
                        text=text,
                    )
                    chunks.append(chunk)
            doc.close()
        except Exception as exc:
            logger.error("pdf_parse_failed", doc_id=doc_id, path=local_path, error=str(exc))
            raise

        logger.info("pdf_parsed", doc_id=doc_id, pages=len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # Parquet persistence
    # ------------------------------------------------------------------

    def save_chunks(self, chunks: list[TextChunk], doc_id: str) -> str:
        """Save TextChunks for a given doc to data/interim/{doc_id}_chunks.parquet."""
        import pandas as pd

        if not chunks:
            logger.warning("no_chunks_to_save", doc_id=doc_id)
            return ""

        records = [c.model_dump(mode="json") for c in chunks]
        df = pd.DataFrame(records)
        out_path = self.interim_dir / f"{doc_id}_chunks.parquet"
        df.to_parquet(str(out_path), index=False)
        logger.info("chunks_saved", doc_id=doc_id, rows=len(chunks), path=str(out_path))
        return str(out_path)

    def load_chunks(self, doc_id: str | None = None) -> list[TextChunk]:
        """Load TextChunks from parquet. If doc_id given, load just that doc."""
        import pandas as pd

        if doc_id:
            path = self.interim_dir / f"{doc_id}_chunks.parquet"
            if not path.exists():
                return []
            df = pd.read_parquet(str(path))
        else:
            files = list(self.interim_dir.glob("*_chunks.parquet"))
            if not files:
                return []
            df = pd.concat([pd.read_parquet(str(f)) for f in files], ignore_index=True)

        chunks: list[TextChunk] = []
        for _, row in df.iterrows():
            chunks.append(TextChunk(**row.to_dict()))
        return chunks

    def parse_all(self, manifest_rows: list) -> list[TextChunk]:  # type: ignore[type-arg]
        """Parse all fetched PDFs from manifest rows and persist to interim parquet."""
        all_chunks: list[TextChunk] = []
        for row in manifest_rows:
            if row.status not in ("fetched", "parsed") or not row.local_path:
                continue
            try:
                chunks = self.parse_pdf(row.local_path, row.doc_id)
                self.save_chunks(chunks, row.doc_id)
                all_chunks.extend(chunks)
                row.status = "parsed"
            except Exception as exc:
                logger.error(
                    "parse_all_failed", doc_id=row.doc_id, error=str(exc)
                )
        return all_chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Collapse excessive whitespace while keeping paragraph structure."""
        import re

        # Collapse multiple blank lines to one
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip trailing whitespace from each line
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines).strip()
