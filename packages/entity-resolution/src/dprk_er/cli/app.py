"""Typer CLI for the DPRK Entity Resolution Engine.

Each command is idempotent and emits structured structlog JSON logs.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog
import typer

app = typer.Typer(
    name="dprk-er",
    help="DPRK Entity Resolution Engine pipeline CLI.",
    add_completion=False,
)

logger = structlog.get_logger(__name__)

_DEFAULT_MANIFEST = "data/raw/manifest.csv"
_DEFAULT_DB_PATH = "data/processed/lancedb"


def _configure_logging() -> None:
    """Configure structlog for the CLI (JSON output to stderr)."""
    import logging

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level, logging.INFO)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("fetch-reports")
def fetch_reports(
    manifest: str = typer.Option(_DEFAULT_MANIFEST, "--manifest", "-m", help="Path to manifest CSV"),
) -> None:
    """Stage 1 – Download PDFs listed in the manifest."""
    _configure_logging()
    from dprk_er.ingest.service import IngestService

    logger.info("fetch_reports_start", manifest=manifest)
    if not Path(manifest).exists():
        typer.echo(f"Manifest not found: {manifest}", err=True)
        raise typer.Exit(code=1)

    svc = IngestService()
    rows = svc.fetch_all(manifest)
    fetched = sum(1 for r in rows if r.status == "fetched")
    failed = sum(1 for r in rows if r.status == "failed")
    logger.info("fetch_reports_done", fetched=fetched, failed=failed)
    if failed:
        typer.echo(f"WARNING: {failed} reports failed to download.", err=True)


@app.command("parse-pdfs")
def parse_pdfs(
    manifest: str = typer.Option(_DEFAULT_MANIFEST, "--manifest", "-m", help="Path to manifest CSV"),
) -> None:
    """Stage 2 – Extract text from downloaded PDFs."""
    _configure_logging()
    from dprk_er.ingest.service import IngestService
    from dprk_er.parse.service import ParseService

    logger.info("parse_pdfs_start")
    ingest_svc = IngestService()
    rows = ingest_svc.load_manifest(manifest)
    parse_svc = ParseService()
    chunks = parse_svc.parse_all(rows)
    ingest_svc.save_manifest(rows, manifest)
    logger.info("parse_pdfs_done", chunks=len(chunks))


@app.command("extract-mentions")
def extract_mentions(
    manifest: str = typer.Option(_DEFAULT_MANIFEST, "--manifest", "-m", help="Path to manifest CSV"),
    db_path: str = typer.Option(_DEFAULT_DB_PATH, "--db-path", help="LanceDB path"),
    extractor: str = typer.Option("gliner", "--extractor", help="Extractor backend: gliner or huggingface"),
) -> None:
    """Stage 3 – Run NER to extract entity mentions from text chunks."""
    _configure_logging()
    from dprk_er.extract.service import ExtractService
    from dprk_er.ingest.service import IngestService
    from dprk_er.parse.service import ParseService
    from dprk_er.storage.lancedb_store import LanceDBStore

    logger.info("extract_mentions_start")
    ingest_svc = IngestService()
    rows = ingest_svc.load_manifest(manifest)
    parse_svc = ParseService()
    extract_svc = ExtractService(extractor_kind=extractor)
    store = LanceDBStore(db_path=db_path)

    all_mentions = []
    for row in rows:
        if row.status not in ("fetched", "parsed") or not row.local_path:
            continue
        chunks = parse_svc.load_chunks(doc_id=row.doc_id)
        if not chunks:
            # Try parsing on-demand
            try:
                chunks = parse_svc.parse_pdf(row.local_path, row.doc_id)
                parse_svc.save_chunks(chunks, row.doc_id)
            except Exception as exc:
                logger.warning("on_demand_parse_failed", doc_id=row.doc_id, error=str(exc))
                continue
        mentions = extract_svc.extract_mentions(chunks, row.doc_id)
        all_mentions.extend(mentions)

    store.upsert_mentions(all_mentions)
    logger.info("extract_mentions_done", mentions=len(all_mentions))


@app.command("embed-mentions")
def embed_mentions(
    db_path: str = typer.Option(_DEFAULT_DB_PATH, "--db-path", help="LanceDB path"),
    batch_size: int = typer.Option(64, "--batch-size", help="Embedding batch size"),
) -> None:
    """Stage 4 – Embed all mentions that lack embeddings."""
    _configure_logging()
    from dprk_er.embed.service import EmbedService
    from dprk_er.storage.lancedb_store import LanceDBStore

    logger.info("embed_mentions_start")
    store = LanceDBStore(db_path=db_path)
    mentions = store.get_mentions()
    to_embed = [m for m in mentions if not m.embedding or all(v == 0.0 for v in (m.embedding or []))]
    logger.info("mentions_to_embed", count=len(to_embed))
    if not to_embed:
        logger.info("all_mentions_already_embedded")
        return

    embed_svc = EmbedService()
    embedded = embed_svc.embed_batch(to_embed, batch_size=batch_size)
    store.upsert_mentions(embedded)
    logger.info("embed_mentions_done", embedded=len(embedded))


@app.command("resolve-aliases")
def resolve_aliases(
    db_path: str = typer.Option(_DEFAULT_DB_PATH, "--db-path", help="LanceDB path"),
    threshold: float = typer.Option(0.7, "--threshold", help="Similarity threshold"),
) -> None:
    """Stage 5 – Generate candidate alias pairs and clusters."""
    _configure_logging()
    from dprk_er.resolve.service import ResolveService
    from dprk_er.storage.lancedb_store import LanceDBStore

    logger.info("resolve_aliases_start", threshold=threshold)
    store = LanceDBStore(db_path=db_path)
    mentions = store.get_mentions()
    embedded = [m for m in mentions if m.embedding]

    svc = ResolveService()
    pairs = svc.generate_candidates(embedded, threshold=threshold)
    clusters = svc.build_clusters(pairs)

    store.upsert_candidates(pairs)
    store.upsert_clusters(clusters)
    logger.info(
        "resolve_aliases_done",
        pairs=len(pairs),
        clusters=len(clusters),
    )


@app.command("run-evals")
def run_evals() -> None:
    """Run all eval suites (ingest, schema, resolution, regression)."""
    _configure_logging()
    logger.info("run_evals_start")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-m", "ingest or schema or resolution or regression", "evals/", "-v"],
        check=False,
    )
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)
    logger.info("run_evals_done")


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Bind host"),
    port: int = typer.Option(8000, "--port", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
) -> None:
    """Start the FastAPI review/search server."""
    _configure_logging()
    import uvicorn  # type: ignore[import-untyped]

    logger.info("serve_start", host=host, port=port)
    uvicorn.run(
        "dprk_er.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
