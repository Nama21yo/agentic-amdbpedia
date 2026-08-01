from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from config import Settings
from mcp_server.agent import ReasoningStep, ToolRequest, run_mapping_agent
from mcp_server.server import MappingPayload, find_semantic_match_impl, generate_mapping_syntax_impl
from rag.embeddings import deterministic_dense_vector, lexical_sparse_vector
from rag.indexing import index_corpus
from rag.retrieval import RetrievalCircuitBreaker, search

pytestmark = pytest.mark.e2e

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
COLLECTION = "test_e2e_dbpedia_mapping"


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


@pytest.fixture()
def qdrant_client() -> Any:
    from qdrant_client import QdrantClient

    settings = Settings()
    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    yield client
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)


def test_full_e2e_index_retrieve_agent_generate_xml(qdrant_client: Any) -> None:
    count = index_corpus(
        data_dir=DATA_DIR,
        collection_name=COLLECTION,
        rebuild=True,
        dense_vector_size=16,
        dense_embedder=lambda text: deterministic_dense_vector(text, size=16),
        sparse_embedder=lexical_sparse_vector,
        client=qdrant_client,
    )

    def tool_runner(request: ToolRequest) -> str:
        if request.name == "find_semantic_match":
            return find_semantic_match_impl(
                **request.arguments,
                search_func=lambda query, target_class=None: search(
                    query,
                    target_class=target_class,
                    collection_name=COLLECTION,
                    client=qdrant_client,
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

    assert count >= 36
    assert retrieved_property != "madeUpProperty"
    assert f"<ontologyProperty>{retrieved_property}</ontologyProperty>" in generated
    assert response.final_answer == "Mapping generated with grounded XML."
