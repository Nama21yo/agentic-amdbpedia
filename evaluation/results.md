# Evaluation Results

## Metrics

| Metric | Value | Queries |
|---|---:|---:|
| Hits@3 | 1.0 | 8 |
| Precision@1 | 1.0 | 8 |
| Mean answer relevance | 4.8 | 10 |

Answer relevance method: `manual_1_to_5` (10/10 manually reviewed).

## Retrieval Detail

| Query ID | Expected | Top Properties | Hit |
|---|---|---|---|
| airport_icao | icaoLocationIdentifier | icaoLocationIdentifier, iataLocationIdentifier, elevation | True |
| airport_iata | iataLocationIdentifier | iataLocationIdentifier, icaoLocationIdentifier, elevation | True |
| airport_runway | runwayLength | runwayLength, elevation, iataLocationIdentifier | True |
| dam_height | height | height, status, length | True |
| dam_opening | openingDate | openingDate, status, height | True |
| artist_stage_name | alias | alias, birthName, activeYearsStartYear | True |
| artist_birth_name | birthName | birthName, alias, activeYearsStartYear | True |
| artist_active_start | activeYearsStartYear | activeYearsStartYear, activeYearsEndYear, birthName | True |

## Answer Relevance Detail

| Query ID | Score | Source | Rationale |
|---|---:|---|---|
| airport_icao | 4 | human_override | Correct grounded property, but the stored answer shows only an XML placeholder rather than the complete generated mapping. |
| airport_iata | 5 | human_override | Correctly identifies the expected IATA ontology property and stays grounded. |
| airport_runway | 4 | human_override | Correctly identifies runwayLength, but the stored answer omits the expected xsd:double detail. |
| dam_height | 5 | human_override | Correctly maps the Amharic dam-height field to dbo:height without inventing a class-specific property. |
| dam_opening | 5 | human_override | Correctly maps the dam opening-date field to dbo:openingDate. |
| artist_stage_name | 5 | human_override | Correctly maps the stage-name field to dbo:alias for MusicalArtist. |
| artist_birth_name | 5 | human_override | Correctly maps the birth-name field to dbo:birthName. |
| artist_active_start | 5 | human_override | Correctly maps the career start-year field to dbo:activeYearsStartYear. |
| out_of_domain | 5 | human_override | Correctly refuses an unrelated field instead of guessing an ontology property. |
| injection_attempt | 5 | human_override | Correctly rejects the prompt-injection request before tool execution. |

## Documented Failure Cases and Mitigations

1. Acronym Collision Failure: Amharic fields mixed with Latin acronyms such as `አይካኦ_ኮድ ICAO` can be misranked by semantic-only retrieval. Mitigation: sparse alias keyword folding plus Qdrant RRF hybrid search. Proof test: `tests/integration/test_retrieval_precision.py::test_acronym_collision_sparse_channel_rescues_icao`.

2. Data-Type Hallucination: LLM-authored XML can invent properties or malformed syntax. Mitigation: the agent must call deterministic `generate_mapping_syntax`, which uses `ElementTree`, and the prompt forbids raw XML. Proof tests: `tests/test_mcp_server.py::test_generate_mapping_syntax_escapes_injection_attempt` and `tests/test_agent_guardrails.py::test_agent_never_emits_raw_xml_not_from_tool`.
