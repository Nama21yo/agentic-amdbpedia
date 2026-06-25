# Cross-Lingual Knowledge Engineering Assistant

Amharic-to-English DBpedia ontology mapping via hybrid retrieval and MCP tools.

## Domain

This project targets cross-lingual semantic web engineering for Amharic Wikipedia
infobox to English DBpedia ontology mapping. Editors currently spend substantial
time guessing technical ontology property names, while generic translation tools
miss schema-specific terms and acronym-heavy fields such as IATA or ICAO codes.
Retrieval-augmented generation is required because the DBpedia ontology is large,
strictly typed, and changes over time; MCP tools are required so deterministic
code, not an LLM, generates MediaWiki XML and exposes live benchmark resources.

## Architecture

```text
Amharic infobox field
  -> input validation and guardrails
  -> dense + sparse retrieval over DBpedia ontology documents
  -> grounded agent selection from retrieved properties only
  -> MCP tool: deterministic mapping XML generation
  -> MCP resource: evaluation metrics
```

## Current Milestone

Milestone 1 is the knowledge-base collection. It provides a validated markdown
corpus under `data/` and an Amharic-to-English alias dictionary for hard
cross-lingual and acronym cases.

## Development

```bash
just test
just validate-corpus
```

## Claude Desktop

Generate the MCP configuration block for this checkout:

```bash
uv run python scripts/print_desktop_config.py
```

Paste the resulting JSON into `claude_desktop_config.json`, set
`GROQ_API_KEY`, and restart Claude Desktop. The server exposes
`find_semantic_match`, `generate_mapping_syntax`, and
`resources://benchmarks/latest`.
