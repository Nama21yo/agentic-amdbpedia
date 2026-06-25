# Demo Video Script

## Problem

Show an Amharic infobox field such as `አይካኦ_ኮድ` and explain why generic
translation does not reliably produce DBpedia ontology identifiers such as
`icaoLocationIdentifier`.

## Architecture

Show the README architecture diagram. Walk through sanitizer, dense/sparse query
encoding, Qdrant hybrid retrieval, grounded ReAct agent, deterministic MCP XML
tool, and benchmark resource.

## Live Demo

1. Run `just validate-corpus`.
2. Run `docker compose up -d qdrant`.
3. Run `just test-integration`.
4. Show `uv run python scripts/print_desktop_config.py` and the Claude Desktop
   config block.
5. Walk through `examples/demo.md` successful mapping, no-match fallback, and
   injection rejection transcripts.

## Evaluation

Show `evaluation/results.md`, `evaluation/latest_metrics.json`, and
`evaluation/relevance_metrics.json`. Point out Hits@3, relevance scores, and the
two documented mitigated failure cases.

## Security

Show:

- `tests/test_mcp_server.py::test_generate_mapping_syntax_escapes_injection_attempt`
- `tests/test_agent_guardrails.py::test_agent_never_emits_raw_xml_not_from_tool`
- `tests/test_error_handling.py::test_mcp_boundary_maps_qdrant_down_to_client_safe_error`
- `tests/test_observability.py::test_correlation_id_propagates_across_layers`

## Learnings

Hybrid retrieval is necessary for mixed Amharic and acronym-heavy fields. XML
generation must remain deterministic because ontology identifiers and MediaWiki
syntax are strict production artifacts.

## Future Work

Add multi-query/step-back retrieval, consent-gated Databus publishing, and more
source languages beyond Amharic.
