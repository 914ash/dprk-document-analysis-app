.PHONY: bootstrap build-slices embed reduce score viz evals lint typecheck test clean

# Default data directory
DATA_DIR ?= data

bootstrap:
	pip install -e ".[dev]"

build-slices:
	python -m dprk_drift.cli build-slices --data-dir $(DATA_DIR)

embed:
	python -m dprk_drift.cli train-embeddings --data-dir $(DATA_DIR)

reduce:
	python -m dprk_drift.cli reduce-umap --data-dir $(DATA_DIR)

score:
	python -m dprk_drift.cli score-drift --data-dir $(DATA_DIR)

viz:
	python -m dprk_drift.cli render-viz --data-dir $(DATA_DIR)

evals:
	pytest -m "graph_build or temporal or embedding or drift or viz" -v

lint:
	ruff check src/ tests/ evals/ scripts/
	ruff format --check src/ tests/ evals/ scripts/

typecheck:
	mypy src/dprk_drift/

test:
	pytest tests/ -v --tb=short

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/ dist/ build/
