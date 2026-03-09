FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY packages/entity-resolution/pyproject.toml /build/entity-resolution/pyproject.toml
COPY packages/entity-resolution/README.md /build/entity-resolution/README.md
COPY packages/entity-resolution/src /build/entity-resolution/src
RUN pip install --prefix=/install /build/entity-resolution

COPY packages/network-drift/pyproject.toml /build/network-drift/pyproject.toml
COPY packages/network-drift/README.md /build/network-drift/README.md
COPY packages/network-drift/src /build/network-drift/src
RUN pip install --prefix=/install /build/network-drift

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_MODEL=all-MiniLM-L6-v2 \
    LANCEDB_PATH=/workspace/data/processed/lancedb \
    LOG_LEVEL=INFO \
    NODE2VEC_DIMENSIONS=64 \
    NODE2VEC_WALK_LENGTH=30 \
    NODE2VEC_NUM_WALKS=200 \
    NODE2VEC_P=1.0 \
    NODE2VEC_Q=1.0 \
    UMAP_N_NEIGHBORS=15 \
    UMAP_MIN_DIST=0.1 \
    RANDOM_SEED=42 \
    DATA_DIR=/workspace/data

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /workspace

COPY packages/entity-resolution /workspace/packages/entity-resolution
COPY packages/network-drift /workspace/packages/network-drift
COPY docs /workspace/docs
COPY ops/docker/toolkit/entrypoint.sh /workspace/entrypoint.sh

RUN mkdir -p /workspace/data/raw /workspace/data/interim /workspace/data/processed /workspace/data/review \
    && chmod +x /workspace/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["tini", "--", "/workspace/entrypoint.sh"]
CMD ["help"]
