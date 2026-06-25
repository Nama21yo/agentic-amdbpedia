# Cross-Lingual Knowledge Engineering Assistant

Amharic-to-English DBpedia ontology mapping via hybrid retrieval and MCP tools.

This repository implements an AI copilot for cross-lingual semantic web engineering:
Amharic Wikipedia infobox fields are matched against English DBpedia ontology
properties, then rendered into deterministic MediaWiki mapping syntax by MCP tools.

## Current Milestone

Milestone 1 is the knowledge-base collection. It provides a validated markdown
corpus under `data/` and an Amharic-to-English alias dictionary for hard
cross-lingual and acronym cases.

## Development

```bash
uv run pytest
uv run python scripts/validate_corpus.py data
```
