from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rag.predict import (
    DEFAULT_MODEL_ALIAS,
    SUPPORTED_MODELS,
    NoCandidatesFound,
    PredictionResult,
    predict_property,
    resolve_model,
    snap_to_candidate,
)
from rag.retrieval import NoMatchFound, RetrievalCircuitBreaker, SearchResult

ICAO = SearchResult(
    property="icaoLocationIdentifier",
    ontology_class="Airport",
    score=1.0,
    payload={},
)
IATA = SearchResult(
    property="iataLocationIdentifier",
    ontology_class="Airport",
    score=0.6,
    payload={},
)


def _search_func(results: list[Any]) -> Any:
    def _fake(query: str, *, target_class: str | None = None, limit: int = 10) -> list[Any]:
        return results

    return _fake


@dataclass
class FakePrediction:
    property_class: str


class FakeProgram:
    """Mimics a DSPy program's callable interface without any real LLM."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[dict[str, str]] = []

    def __call__(self, *, premise: str, candidates: str) -> FakePrediction:
        self.calls.append({"premise": premise, "candidates": candidates})
        return FakePrediction(property_class=self.answer)


class BrokenProgram:
    def __call__(self, *, premise: str, candidates: str) -> FakePrediction:
        raise TimeoutError("ollama unreachable")


def test_default_model_alias_is_gemma2() -> None:
    assert DEFAULT_MODEL_ALIAS == "gemma2"
    assert SUPPORTED_MODELS["gemma2"].litellm_model == "ollama_chat/gemma2:9b"


def test_resolve_model_looks_up_registry_alias() -> None:
    assert resolve_model("gemma2") == "ollama_chat/gemma2:9b"


def test_resolve_model_passes_through_unknown_names() -> None:
    assert resolve_model("ollama_chat/mistral:7b") == "ollama_chat/mistral:7b"


def test_predict_returns_no_candidates_when_retrieval_finds_nothing() -> None:
    outcome = predict_property(
        "unrelated nonsense", search_func=_search_func([NoMatchFound(query="unrelated nonsense")])
    )

    assert isinstance(outcome, NoCandidatesFound)


def test_predict_uses_llm_reranked_answer_when_program_agrees_with_retriever() -> None:
    program = FakeProgram(answer="icaoLocationIdentifier")

    outcome = predict_property(
        "አይካኦ_ኮድ",
        search_func=_search_func([ICAO, IATA]),
        program=program,
        circuit_breaker=None,
    )

    assert isinstance(outcome, PredictionResult)
    assert outcome.property == "icaoLocationIdentifier"
    assert outcome.used_llm is True
    assert outcome.candidates == ["icaoLocationIdentifier", "iataLocationIdentifier"]
    assert program.calls == [
        {"premise": "አይካኦ_ኮድ", "candidates": "icaoLocationIdentifier; iataLocationIdentifier"}
    ]


def test_predict_lets_llm_override_the_top_retrieval_result() -> None:
    program = FakeProgram(answer="iataLocationIdentifier")

    outcome = predict_property(
        "ambiguous code",
        search_func=_search_func([ICAO, IATA]),
        program=program,
        circuit_breaker=None,
    )

    assert isinstance(outcome, PredictionResult)
    assert outcome.property == "iataLocationIdentifier"
    assert outcome.used_llm is True


def test_snap_to_candidate_keeps_an_already_exact_match() -> None:
    assert snap_to_candidate("icaoLocationIdentifier", ["icaoLocationIdentifier"]) == (
        "icaoLocationIdentifier"
    )


def test_snap_to_candidate_is_case_and_whitespace_insensitive() -> None:
    assert (
        snap_to_candidate("  ICAOLocationIdentifier ", ["icaoLocationIdentifier"])
        == "icaoLocationIdentifier"
    )


def test_snap_to_candidate_fixes_a_near_miss_typo() -> None:
    # The guardrail this ports from LLMIntegration's SelectFromCandidates:
    # never trust an LLM answer verbatim if it's close-but-not-exact.
    assert (
        snap_to_candidate(
            "icaoLocationIdentifer", ["icaoLocationIdentifier", "iataLocationIdentifier"]
        )
        == "icaoLocationIdentifier"
    )


def test_snap_to_candidate_falls_back_to_first_candidate_on_a_hallucinated_answer() -> None:
    assert (
        snap_to_candidate(
            "completelyMadeUpProperty", ["icaoLocationIdentifier", "iataLocationIdentifier"]
        )
        == "icaoLocationIdentifier"
    )


def test_snap_to_candidate_with_no_candidates_returns_answer_unchanged() -> None:
    assert snap_to_candidate("anything", []) == "anything"


def test_predict_falls_back_to_retrieval_top1_when_llm_call_fails() -> None:
    outcome = predict_property(
        "አይካኦ_ኮድ",
        search_func=_search_func([ICAO, IATA]),
        program=BrokenProgram(),
        circuit_breaker=None,
    )

    assert isinstance(outcome, PredictionResult)
    assert outcome.property == "icaoLocationIdentifier"
    assert outcome.used_llm is False
    assert "TimeoutError" in outcome.reason
    assert outcome.top_retrieval_result == ICAO


def test_predict_falls_back_when_circuit_breaker_is_open() -> None:
    breaker = RetrievalCircuitBreaker(failure_threshold=1, reset_after_seconds=60)
    breaker.record_failure()
    assert not breaker.allow_request()

    outcome = predict_property(
        "አይካኦ_ኮድ",
        search_func=_search_func([ICAO, IATA]),
        program=FakeProgram(answer="iataLocationIdentifier"),
        circuit_breaker=breaker,
    )

    assert isinstance(outcome, PredictionResult)
    assert outcome.property == "icaoLocationIdentifier"
    assert outcome.used_llm is False
    assert outcome.reason == "LLM reranking temporarily unavailable"


def test_predict_records_failure_on_circuit_breaker_after_llm_error() -> None:
    breaker = RetrievalCircuitBreaker(failure_threshold=1, reset_after_seconds=60)

    predict_property(
        "አይካኦ_ኮድ",
        search_func=_search_func([ICAO]),
        program=BrokenProgram(),
        circuit_breaker=breaker,
    )

    assert not breaker.allow_request()


@pytest.mark.integration
def test_real_dspy_program_construction_and_offline_fallback() -> None:
    """No Ollama is expected to be reachable in CI/test environments — this
    exercises the real (not injected) DSPy program construction path end to
    end and confirms it degrades gracefully rather than raising."""

    outcome = predict_property(
        "አይካኦ_ኮድ",
        search_func=_search_func([ICAO, IATA]),
        circuit_breaker=None,
    )

    assert isinstance(outcome, PredictionResult)
    # Either a real Ollama happened to be reachable (used_llm=True, some
    # candidate chosen) or it wasn't (graceful fallback to top-1) — both are
    # correct outcomes; what must never happen is an unhandled exception.
    assert outcome.property in {"icaoLocationIdentifier", "iataLocationIdentifier"}
