"""Standalone script: compute Node2Vec embeddings for each annual slice.

Usage:
    python scripts/run_embeddings.py [--data-dir data] [--dimensions 64] [--num-walks 200]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dprk_drift.embed.service import EmbedService
from dprk_drift.slice.service import SliceService
from dprk_drift.types.models import EmbeddingConfig


def main(
    data_dir: str = "data",
    dimensions: int = 64,
    walk_length: int = 30,
    num_walks: int = 200,
    p: float = 1.0,
    q: float = 1.0,
    seed: int = 42,
    slices_dir: str | None = None,
    output_dir: str | None = None,
) -> None:
    data_path = Path(data_dir)
    in_dir = Path(slices_dir) if slices_dir else data_path / "interim" / "slices"
    out_dir = Path(output_dir) if output_dir else data_path / "interim" / "embeddings"

    if not in_dir.exists():
        print(f"ERROR: Slices directory not found: {in_dir}")
        print("Run scripts/build_slices.py first.")
        sys.exit(1)

    config = EmbeddingConfig(
        dimensions=dimensions,
        walk_length=walk_length,
        num_walks=num_walks,
        p=p,
        q=q,
        random_seed=seed,
        version="v1",
    )

    print(f"Embedding config: {config.model_dump()}")

    sl = SliceService()
    em = EmbedService(config)

    slices = sl.load_slices(str(in_dir))
    print(f"Loaded {len(slices)} slices: {sorted(slices.keys())}")

    all_embeddings = em.embed_all_slices(slices)
    em.save_embeddings(all_embeddings, str(out_dir))

    total = sum(len(v) for v in all_embeddings.values())
    print(f"Generated {total} embeddings across {len(all_embeddings)} slices → {out_dir}")

    for year, emb_list in sorted(all_embeddings.items()):
        print(f"  Slice {year}: {len(emb_list)} embeddings × {config.dimensions} dims")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute Node2Vec embeddings")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--dimensions", type=int, default=64)
    parser.add_argument("--walk-length", type=int, default=30)
    parser.add_argument("--num-walks", type=int, default=200)
    parser.add_argument("--p", type=float, default=1.0)
    parser.add_argument("--q", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--slices-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    os.chdir(Path(__file__).parent.parent)
    main(
        data_dir=args.data_dir,
        dimensions=args.dimensions,
        walk_length=args.walk_length,
        num_walks=args.num_walks,
        p=args.p,
        q=args.q,
        seed=args.seed,
        slices_dir=args.slices_dir,
        output_dir=args.output_dir,
    )
