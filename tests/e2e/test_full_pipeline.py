from __future__ import annotations

import json
from typing import Any

import pytest

from mcp_server.agent import ReasoningStep, ToolRequest, run_mapping_agent
from mcp_server.server import MappingPayload, find_semantic_match_impl, generate_mapping_syntax_impl
from rag.corpus import build_corpus
from rag.embeddings import deterministic_dense_vector, lexical_sparse_vector
from rag.retrieval import RetrievalCircuitBreaker, search

pytestmark = pytest.mark.e2e


class ScriptedGroq:
    def __init__(self) -> None:
        self.steps = [
            ReasoningStep(
                tool_call=ToolRequest(
                    "find_semantic_match",
                    {"amharic_property": "አይካኦ_ኮድ", "target_class": "Airport"},
                )
            ),
            ReasoningStep(
                tool_call=ToolRequest(
                    "generate_mapping_syntax",
                    {
                        "domain_class": "Airport",
                        "mappings": [
                            {
                                "templateProperty": "አይካኦ_ኮድ",
                                "ontologyProperty": "madeUpProperty",
                            }
                        ],
                    },
                )
            ),
            ReasoningStep(content="Mapping generated with grounded XML.", final=True),
        ]
        self.index = 0

    def reason(self, _: list[dict[str, Any]], __: list[dict[str, Any]]) -> ReasoningStep:
        step = self.steps[self.index]
        self.index += 1
        return step


def test_full_e2e_retrieve_agent_generate_xml() -> None:
    # The real ~2,948-property corpus with fake 16-dim hash embeddings would
    # produce noisy dense-channel ties at this scale (many properties share
    # a rank-1 collision with an all-hash, non-semantic vector space) — this
    # test exercises the full plumbing (retrieval -> agent -> XML), not
    # retrieval quality, so a small deterministic corpus keeps it fast and
    # stable, same as tests/test_retrieval.py.
    corpus = build_corpus()
    icao_doc = next(doc for doc in corpus if doc.property == "icaoLocationIdentifier")

    def tool_runner(request: ToolRequest) -> str:
        if request.name == "find_semantic_match":
            return find_semantic_match_impl(
                **request.arguments,
                search_func=lambda query, target_class=None: search(
                    query,
                    target_class=target_class,
                    corpus=[icao_doc],
                    dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
                    sparse_embedder=lexical_sparse_vector,
                    confidence_threshold=0.1,
                    circuit_breaker=RetrievalCircuitBreaker(),
                ),
            )
        if request.name == "generate_mapping_syntax":
            return generate_mapping_syntax_impl(MappingPayload.model_validate(request.arguments))
        raise AssertionError(f"unexpected tool {request.name}")

    response = run_mapping_agent(
        "አይካኦ_ኮድ ICAO",
        target_class="Airport",
        groq_client=ScriptedGroq(),
        tool_runner=tool_runner,
    )

    generated = response.trace[2].detail["observation"]
    retrieval_payload = json.loads(response.trace[1].detail["observation"])

    retrieved_property = retrieval_payload["matches"][0]["property"]

    assert retrieved_property == "icaoLocationIdentifier"
    assert retrieved_property != "madeUpProperty"
    assert f"<ontologyProperty>{retrieved_property}</ontologyProperty>" in generated
    assert response.final_answer == "Mapping generated with grounded XML."
