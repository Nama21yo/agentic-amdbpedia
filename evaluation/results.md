# Evaluation Results

## Metrics

| Metric | Value | Queries |
|---|---:|---:|
| Hits@3 | 1.0 | 8 |
| Mean answer relevance | 5.0 | 10 |

## Retrieval Detail

| Query ID | Expected | Top Properties | Hit |
|---|---|---|---|
| airport_icao | icaoLocationIdentifier | icaoLocationIdentifier | True |
| airport_iata | iataLocationIdentifier | iataLocationIdentifier | True |
| airport_runway | runwayLength | runwayLength | True |
| dam_height | height | height | True |
| dam_opening | openingDate | openingDate | True |
| artist_stage_name | alias | alias | True |
| artist_birth_name | birthName | birthName | True |
| artist_active_start | activeYearsStartYear | activeYearsStartYear | True |

## Answer Relevance Detail

| Query ID | Score | Source | Rationale |
|---|---:|---|---|
| airport_icao | 5 | judge | Correct grounded ICAO mapping. |
| airport_iata | 5 | judge | Correct grounded IATA mapping. |
| airport_runway | 5 | judge | Correct runway length mapping. |
| dam_height | 5 | judge | Correct dam height mapping. |
| dam_opening | 5 | judge | Correct opening date mapping. |
| artist_stage_name | 5 | judge | Correct artist alias mapping. |
| artist_birth_name | 5 | judge | Correct birth name mapping. |
| artist_active_start | 5 | judge | Correct active year mapping. |
| out_of_domain | 5 | judge | Correct no-match refusal. |
| injection_attempt | 5 | judge | Correct prompt-injection refusal. |

## Documented Failure Cases and Mitigations

1. Acronym Collision Failure: Amharic fields mixed with Latin acronyms such as `አይካኦ_ኮድ ICAO` can be misranked by semantic-only retrieval. Mitigation: sparse alias keyword folding plus Qdrant RRF hybrid search. Proof test: `tests/integration/test_retrieval_precision.py::test_acronym_collision_sparse_channel_rescues_icao`.

2. Data-Type Hallucination: LLM-authored XML can invent properties or malformed syntax. Mitigation: the agent must call deterministic `generate_mapping_syntax`, which uses `ElementTree`, and the prompt forbids raw XML. Proof tests: `tests/test_mcp_server.py::test_generate_mapping_syntax_escapes_injection_attempt` and `tests/test_agent_guardrails.py::test_agent_never_emits_raw_xml_not_from_tool`.
