"""Typer CLI for the DPRK Temporal Network Drift Engine.

Commands:
    build-slices      — Load entities/relations, build annual graph slices
    train-embeddings  — Compute Node2Vec embeddings per slice
    reduce-umap       — Run UMAP dimensionality reduction
    score-drift       — Compute entity drift scores
    render-viz        — Generate Plotly visualizations
    run-evals         — Run pytest evaluation suite

Each command logs its deterministic config, saves versioned outputs, and fails
loudly on schema mismatch.

Layer: cli (orchestrates all other layers; contains NO business logic)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog
import typer
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

logger = structlog.get_logger(__name__)

app = typer.Typer(
    name="dprk-drift",
    help="DPRK Temporal Network Drift Engine — temporal graph analytics pipeline.",
    add_completion=False,
)


def _configure_structlog() -> None:
    """Configure structlog for deterministic, structured output."""
    import structlog

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _get_embedding_config():
    """Load EmbeddingConfig from environment variables."""
    from dprk_drift.types.models import EmbeddingConfig

    return EmbeddingConfig(
        dimensions=int(os.getenv("NODE2VEC_DIMENSIONS", "64")),
        walk_length=int(os.getenv("NODE2VEC_WALK_LENGTH", "30")),
        num_walks=int(os.getenv("NODE2VEC_NUM_WALKS", "200")),
        p=float(os.getenv("NODE2VEC_P", "1.0")),
        q=float(os.getenv("NODE2VEC_Q", "1.0")),
        random_seed=int(os.getenv("RANDOM_SEED", "42")),
        version="v1",
    )


@app.command(name="build-slices")
def build_slices(
    data_dir: str = typer.Option(
        os.getenv("DATA_DIR", "data"),
        "--data-dir",
        "-d",
        help="Root data directory containing fixtures/",
    ),
    fixture: bool = typer.Option(
        False,
        "--fixture",
        help="Use fixture data for fast testing",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Override output directory (default: {data_dir}/interim/slices)",
    ),
) -> None:
    """Load entity/relation parquet files and build annual graph slices."""
    _configure_structlog()

    from dprk_drift.graph_build.service import GraphBuildService
    from dprk_drift.slice.service import SliceService

    # Resolve paths
    data_path = Path(data_dir)
    fixtures_dir = data_path / "fixtures"
    out_dir = Path(output_dir) if output_dir else data_path / "interim" / "slices"

    entities_path = fixtures_dir / "entities.parquet"
    relations_path = fixtures_dir / "relations.parquet"

    logger.info(
        "build_slices_start",
        entities_path=str(entities_path),
        relations_path=str(relations_path),
        output_dir=str(out_dir),
    )

    # Validate inputs exist
    if not entities_path.exists():
        logger.error("entities_not_found", path=str(entities_path))
        raise typer.Exit(code=1)
    if not relations_path.exists():
        logger.error("relations_not_found", path=str(relations_path))
        raise typer.Exit(code=1)

    try:
        graph_svc = GraphBuildService()
        slice_svc = SliceService()

        nodes = graph_svc.load_entities(str(entities_path))
        edges = graph_svc.load_relations(str(relations_path))

        logger.info("data_loaded", nodes=len(nodes), edges=len(edges))

        slices = slice_svc.build_annual_slices(nodes, edges)
        logger.info("slices_built", count=len(slices), years=sorted(slices.keys()))

        slice_svc.save_slices(slices, str(out_dir))

        typer.echo(f"✓ Built {len(slices)} annual slices → {out_dir}")
    except Exception as err:
        logger.error("build_slices_failed", error=str(err))
        typer.echo(f"✗ build-slices failed: {err}", err=True)
        raise typer.Exit(code=1) from err


@app.command(name="train-embeddings")
def train_embeddings(
    data_dir: str = typer.Option(
        os.getenv("DATA_DIR", "data"),
        "--data-dir",
        "-d",
        help="Root data directory",
    ),
    fixture: bool = typer.Option(
        False,
        "--fixture",
        help="Use fixture data for fast testing",
    ),
    slices_dir: str | None = typer.Option(
        None,
        "--slices-dir",
        help="Override slices input directory",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Override embeddings output directory",
    ),
) -> None:
    """Compute Node2Vec embeddings for each annual graph slice."""
    _configure_structlog()

    from dprk_drift.embed.service import EmbedService
    from dprk_drift.slice.service import SliceService

    data_path = Path(data_dir)
    in_dir = Path(slices_dir) if slices_dir else data_path / "interim" / "slices"
    out_dir = Path(output_dir) if output_dir else data_path / "interim" / "embeddings"

    config = _get_embedding_config()

    logger.info(
        "train_embeddings_start",
        slices_dir=str(in_dir),
        output_dir=str(out_dir),
        config=config.model_dump(),
    )

    if not in_dir.exists():
        logger.error("slices_dir_not_found", path=str(in_dir))
        raise typer.Exit(code=1)

    try:
        slice_svc = SliceService()
        embed_svc = EmbedService(config)

        slices = slice_svc.load_slices(str(in_dir))
        logger.info("slices_loaded", count=len(slices), years=sorted(slices.keys()))

        all_embeddings = embed_svc.embed_all_slices(slices)
        embed_svc.save_embeddings(all_embeddings, str(out_dir))

        total = sum(len(v) for v in all_embeddings.values())
        typer.echo(f"✓ Generated {total} embeddings across {len(all_embeddings)} slices → {out_dir}")
    except Exception as err:
        logger.error("train_embeddings_failed", error=str(err))
        typer.echo(f"✗ train-embeddings failed: {err}", err=True)
        raise typer.Exit(code=1) from err


@app.command(name="reduce-umap")
def reduce_umap(
    data_dir: str = typer.Option(
        os.getenv("DATA_DIR", "data"),
        "--data-dir",
        "-d",
        help="Root data directory",
    ),
    fixture: bool = typer.Option(
        False,
        "--fixture",
        help="Use fixture data for fast testing",
    ),
    embeddings_dir: str | None = typer.Option(
        None,
        "--embeddings-dir",
        help="Override embeddings input directory",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Override viz points output directory",
    ),
    n_neighbors: int = typer.Option(
        int(os.getenv("UMAP_N_NEIGHBORS", "15")),
        "--n-neighbors",
        help="UMAP n_neighbors",
    ),
    min_dist: float = typer.Option(
        float(os.getenv("UMAP_MIN_DIST", "0.1")),
        "--min-dist",
        help="UMAP min_dist",
    ),
) -> None:
    """Run UMAP dimensionality reduction on embeddings for visualization."""
    _configure_structlog()

    from dprk_drift.embed.service import EmbedService
    from dprk_drift.reduce.service import ReduceService

    data_path = Path(data_dir)
    in_dir = Path(embeddings_dir) if embeddings_dir else data_path / "interim" / "embeddings"
    out_dir = Path(output_dir) if output_dir else data_path / "interim" / "reduced"

    config = _get_embedding_config()
    seed = config.random_seed

    logger.info(
        "reduce_umap_start",
        embeddings_dir=str(in_dir),
        output_dir=str(out_dir),
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        seed=seed,
    )

    if not in_dir.exists():
        logger.error("embeddings_dir_not_found", path=str(in_dir))
        raise typer.Exit(code=1)

    try:
        embed_svc = EmbedService(config)
        reduce_svc = ReduceService(n_neighbors=n_neighbors, min_dist=min_dist, random_seed=seed)

        all_embeddings = embed_svc.load_embeddings(str(in_dir))
        logger.info("embeddings_loaded", slices=len(all_embeddings))

        viz_points = reduce_svc.reduce_all_slices(all_embeddings, joint=True)
        reduce_svc.save_viz_points(viz_points, str(out_dir))

        total = sum(len(v) for v in viz_points.values())
        typer.echo(f"✓ Reduced {total} points to 2D across {len(viz_points)} slices → {out_dir}")
    except Exception as err:
        logger.error("reduce_umap_failed", error=str(err))
        typer.echo(f"✗ reduce-umap failed: {err}", err=True)
        raise typer.Exit(code=1) from err


@app.command(name="score-drift")
def score_drift(
    data_dir: str = typer.Option(
        os.getenv("DATA_DIR", "data"),
        "--data-dir",
        "-d",
        help="Root data directory",
    ),
    fixture: bool = typer.Option(
        False,
        "--fixture",
        help="Use fixture data for fast testing",
    ),
    slices_dir: str | None = typer.Option(
        None,
        "--slices-dir",
        help="Override slices input directory",
    ),
    embeddings_dir: str | None = typer.Option(
        None,
        "--embeddings-dir",
        help="Override embeddings input directory",
    ),
    output_path: str | None = typer.Option(
        None,
        "--output-path",
        help="Override drift scores output parquet path",
    ),
) -> None:
    """Compute multi-signal drift scores for all entities across adjacent slices."""
    _configure_structlog()

    from dprk_drift.embed.service import EmbedService
    from dprk_drift.score.service import ScoreService
    from dprk_drift.slice.service import SliceService

    data_path = Path(data_dir)
    slices_in = Path(slices_dir) if slices_dir else data_path / "interim" / "slices"
    emb_in = Path(embeddings_dir) if embeddings_dir else data_path / "interim" / "embeddings"
    scores_out = Path(output_path) if output_path else data_path / "processed" / "drift_scores.parquet"

    config = _get_embedding_config()

    logger.info(
        "score_drift_start",
        slices_dir=str(slices_in),
        embeddings_dir=str(emb_in),
        output_path=str(scores_out),
    )

    for p in [slices_in, emb_in]:
        if not p.exists():
            logger.error("input_dir_not_found", path=str(p))
            raise typer.Exit(code=1)

    try:
        slice_svc = SliceService()
        embed_svc = EmbedService(config)
        score_svc = ScoreService()

        slices = slice_svc.load_slices(str(slices_in))
        all_embeddings = embed_svc.load_embeddings(str(emb_in))

        scores = score_svc.score_all_entities(slices, all_embeddings)
        score_svc.save_scores(scores, str(scores_out))

        if scores:
            avg_composite = sum(s.composite_score for s in scores) / len(scores)
            top3 = sorted(scores, key=lambda s: s.composite_score, reverse=True)[:3]
            logger.info(
                "score_summary",
                total=len(scores),
                avg_composite=round(avg_composite, 4),
                top_entities=[s.entity_id for s in top3],
            )

        typer.echo(f"✓ Computed {len(scores)} drift scores → {scores_out}")
    except Exception as err:
        logger.error("score_drift_failed", error=str(err))
        typer.echo(f"✗ score-drift failed: {err}", err=True)
        raise typer.Exit(code=1) from err


@app.command(name="render-viz")
def render_viz(
    data_dir: str = typer.Option(
        os.getenv("DATA_DIR", "data"),
        "--data-dir",
        "-d",
        help="Root data directory",
    ),
    fixture: bool = typer.Option(
        False,
        "--fixture",
        help="Use fixture data for fast testing",
    ),
    viz_points_dir: str | None = typer.Option(
        None,
        "--viz-points-dir",
        help="Override viz points input directory",
    ),
    scores_path: str | None = typer.Option(
        None,
        "--scores-path",
        help="Override drift scores parquet path",
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output-dir",
        help="Override visualization HTML output directory",
    ),
    top_n: int = typer.Option(20, "--top-n", help="Number of top drifters to show"),
) -> None:
    """Generate Plotly HTML visualization artifacts."""
    _configure_structlog()

    from dprk_drift.reduce.service import ReduceService
    from dprk_drift.score.service import ScoreService
    from dprk_drift.visualize.service import VisualizeService

    data_path = Path(data_dir)
    vp_dir = Path(viz_points_dir) if viz_points_dir else data_path / "interim" / "reduced"
    sc_path = Path(scores_path) if scores_path else data_path / "processed" / "drift_scores.parquet"
    out_dir = Path(output_dir) if output_dir else data_path / "processed" / "viz"

    logger.info(
        "render_viz_start",
        viz_points_dir=str(vp_dir),
        scores_path=str(sc_path),
        output_dir=str(out_dir),
    )

    try:
        reduce_svc = ReduceService()
        score_svc = ScoreService()
        viz_svc = VisualizeService()

        # Load inputs
        viz_points = reduce_svc.load_viz_points(str(vp_dir)) if vp_dir.exists() else {}
        drift_scores = score_svc.load_scores(str(sc_path)) if sc_path.exists() else []

        # Enrich viz points with drift scores
        if drift_scores and viz_points:
            # Use max composite score per entity across all transitions
            max_scores: dict[str, float] = {}
            for s in drift_scores:
                if s.entity_id not in max_scores or s.composite_score > max_scores[s.entity_id]:
                    max_scores[s.entity_id] = s.composite_score
            viz_points = reduce_svc.enrich_with_drift_scores(viz_points, max_scores)

        # Get top drifters for highlight
        top_drifters = score_svc.get_top_drifters(drift_scores, top_n=10)
        highlight_ids = list({s.entity_id for s in top_drifters})

        saved = viz_svc.save_all_viz(
            output_dir=str(out_dir),
            viz_points=viz_points,
            drift_scores=drift_scores,
            highlight_ids=highlight_ids,
            top_n=top_n,
        )

        typer.echo(f"✓ Generated {len(saved)} visualizations → {out_dir}")
        for name, path in saved.items():
            typer.echo(f"  • {name}: {path}")
    except Exception as err:
        logger.error("render_viz_failed", error=str(err))
        typer.echo(f"✗ render-viz failed: {err}", err=True)
        raise typer.Exit(code=1) from err


@app.command(name="run-evals")
def run_evals(
    markers: str = typer.Option(
        "graph_build or temporal or embedding or drift or viz",
        "--markers",
        "-m",
        help="Pytest marker expression",
    ),
    verbose: bool = typer.Option(True, "--verbose/--quiet", "-v/-q"),
) -> None:
    """Run the evaluation test suite with pytest markers."""
    _configure_structlog()

    cmd = [
        sys.executable, "-m", "pytest",
        "-m", markers,
        "--tb=short",
    ]
    if verbose:
        cmd.append("-v")

    logger.info("run_evals_start", command=" ".join(cmd))

    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent.parent.parent.parent)
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)

    typer.echo("✓ All evals passed")
