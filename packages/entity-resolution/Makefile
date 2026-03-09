.PHONY: bootstrap bootstrap-baseline ingest parse extract embed resolve review evals lint typecheck test serve

# ── Bootstrap ────────────────────────────────────────────────────────────────
bootstrap:
	pip install -e ".[dev]"

bootstrap-baseline:
	pip install -e ".[dev]"
	python -m spacy download en_core_web_sm

# ── Pipeline stages ───────────────────────────────────────────────────────────
ingest:
	python -m dprk_er.cli fetch-reports

parse:
	python -m dprk_er.cli parse-pdfs

extract:
	python -m dprk_er.cli extract-mentions

embed:
	python -m dprk_er.cli embed-mentions

resolve:
	python -m dprk_er.cli resolve-aliases

review:
	python -m dprk_er.cli serve

# ── Quality ───────────────────────────────────────────────────────────────────
lint:
	ruff check src tests evals scripts
	ruff format --check src tests evals scripts

typecheck:
	mypy src

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

evals:
	pytest -m "ingest or schema or resolution or regression" evals/ -v

# ── Dev server ────────────────────────────────────────────────────────────────
serve:
	python -m dprk_er.cli serve
