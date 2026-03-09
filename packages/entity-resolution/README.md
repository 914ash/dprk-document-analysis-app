# Entity Resolution Package

Canonical package for DPRK mention extraction, embedding, alias scoring, and analyst review.

## Highlights
- GLiNER-backed extractor adapter with a Hugging Face fallback contract.
- Sentence-transformers embeddings for contextual mention similarity.
- Structured candidate evidence for review UIs and downstream dashboard export.
- LanceDB-backed mention, candidate, and cluster storage.

## Key command
- `python -m dprk_er.cli extract-mentions --extractor gliner`
