"""Gemma 2 9B retrieve-then-rerank predictor.

Ported from `LLMIntegration/models.py` and `llm_raranker.py` (refs
implementation.md 11.1/11.2). LLMIntegration's own script computed its
top-k candidates directly from a SentenceTransformer over a fixed label
set; here candidates come from `rag.retrieval.search()` instead — the same
real ontology corpus, dense+sparse retrieval, and confidence logic already
used everywhere else in this repo.

The retriever alone already picks a top-1 answer; this module lets a local
LLM (Gemma 2 9B by default, via Ollama/LiteLLM) rerank among the retriever's
own top-k candidates. It is an enhancement, never a dependency: a missing
or unreachable Ollama, or an open circuit breaker, degrades to the
retriever's own top-1 choice with `used_llm=False` rather than a failed
request (refs 11.2).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from rapidfuzz import fuzz

from logging_config import log_event
from rag.retrieval import RetrievalCircuitBreaker, RetrievalResult, SearchResult, search

LOGGER = logging.getLogger("dbpedia_mapping_assistant.predict")

SearchFunc = Callable[..., list[RetrievalResult]]

FUZZY_THRESHOLD = 85
DEFAULT_MODEL_ALIAS = "gemma2"
DEFAULT_TOP_K = 10


@dataclass(frozen=True)
class ModelConfig:
    alias: str
    litellm_model: str
    description: str


SUPPORTED_MODELS: dict[str, ModelConfig] = {
    "gemma2": ModelConfig(
        alias="gemma2",
        litellm_model="ollama_chat/gemma2:9b",
        description="Gemma 2 9B Instruct (default)",
    ),
    "qwen2.5:32b": ModelConfig(
        alias="qwen2.5:32b",
        litellm_model="ollama_chat/qwen2.5:32b",
        description="Qwen 2.5 32B",
    ),
    "llama3.1": ModelConfig(
        alias="llama3.1",
        litellm_model="ollama_chat/llama3.1:8b",
        description="Llama 3.1 8B Instruct",
    ),
    "llama3.2": ModelConfig(
        alias="llama3.2",
        litellm_model="ollama_chat/llama3.2:3b",
        description="Llama 3.2 3B Instruct",
    ),
    "aya": ModelConfig(
        alias="aya",
        litellm_model="ollama_chat/aya-expanse:8b",
        description="Aya Expanse 8B",
    ),
}


def resolve_model(name: str) -> str:
    """Resolve a registry alias to its LiteLLM model string.

    Falls back to returning `name` unchanged, so a new Ollama tag or any
    other LiteLLM-compatible model string still works without a registry
    entry.
    """

    config = SUPPORTED_MODELS.get(name)
    return config.litellm_model if config else name


def _normalize(text: str) -> str:
    return " ".join(str(text).strip().casefold().split())


def snap_to_candidate(answer: str, candidates: list[str]) -> str:
    """Never let an answer leave this module unless it's one of the
    retriever's own candidates — the core guardrail ported from
    LLMIntegration's SelectFromCandidates, kept standalone and directly
    testable rather than buried inside the DSPy module closure.

    Always returns one of `candidates` verbatim, never the LLM's own
    echoed casing/whitespace — downstream XML generation is case-sensitive
    about real DBpedia ontology property names, so an exact normalized
    match still snaps to the candidate's canonical spelling rather than
    trusting the answer text as-is (a deliberate change from
    LLMIntegration's original, which only ever fed its output into an
    accuracy metric, not a case-sensitive XML pipeline). A fuzzy-close match
    also snaps to its nearest candidate; anything else falls back to the
    retriever's own top-ranked candidate rather than trusting an
    unrecognized answer.
    """

    if not candidates:
        return answer
    best = max(candidates, key=lambda candidate: fuzz.token_sort_ratio(candidate, answer))
    if _normalize(best) == _normalize(answer) or fuzz.token_sort_ratio(best, answer) >= (
        FUZZY_THRESHOLD
    ):
        return best
    return candidates[0]


class DspyPrediction(Protocol):
    property_class: str


class DspyProgram(Protocol):
    def __call__(self, *, premise: str, candidates: str) -> DspyPrediction: ...


def _build_dspy_program() -> DspyProgram:
    """Construct the real DSPy program. Deferred import: dspy is only ever
    needed when a caller actually wants LLM reranking, not for plain
    retrieval-only usage."""

    import dspy

    class PropertyMappingMC(dspy.Signature):  # type: ignore[misc]
        """Choose the correct canonical English property class for a
        (possibly Amharic) infobox property mention. The premise has the
        form "<entity type>'s <property mention>". You are given candidate
        classes ORDERED BY RETRIEVER CONFIDENCE (most likely first). The
        first candidate is usually correct: keep it unless another
        candidate clearly matches the property mention better. Answer with
        exactly one class copied verbatim from the candidate list."""

        premise: str = dspy.InputField()
        candidates: str = dspy.InputField()
        property_class: str = dspy.OutputField()

    class SelectFromCandidates(dspy.Module):  # type: ignore[misc]
        """Guardrail wrapper: never let the LLM answer with a property that
        isn't one of the retriever's own candidates."""

        def __init__(self, inner: Any) -> None:
            super().__init__()
            self.inner = inner

        def forward(self, **kwargs: Any) -> Any:
            pred = self.inner(**kwargs)
            candidates = [c for c in kwargs.get("candidates", "").split("; ") if c]
            pred.property_class = snap_to_candidate(pred.property_class, candidates)
            return pred

    return SelectFromCandidates(dspy.Predict(PropertyMappingMC))


def _call_dspy(
    program: DspyProgram, amharic_property: str, candidates: list[str], model_alias: str
) -> str:
    import dspy

    lm = dspy.LM(resolve_model(model_alias), temperature=0.0, max_tokens=256)
    with dspy.context(lm=lm):
        prediction = program(premise=amharic_property, candidates="; ".join(candidates))
    return prediction.property_class


@dataclass(frozen=True)
class PredictionResult:
    """The final chosen property, plus enough context to explain the choice."""

    property: str
    used_llm: bool
    candidates: list[str]
    top_retrieval_result: SearchResult | None
    reason: str = ""


@dataclass(frozen=True)
class NoCandidatesFound:
    query: str
    reason: str = "No retrieval candidates to rerank"


PredictOutcome = PredictionResult | NoCandidatesFound

DEFAULT_PREDICT_CIRCUIT_BREAKER = RetrievalCircuitBreaker()


def predict_property(
    amharic_property: str,
    *,
    target_class: str | None = None,
    model_alias: str = DEFAULT_MODEL_ALIAS,
    top_k: int = DEFAULT_TOP_K,
    program: DspyProgram | None = None,
    circuit_breaker: RetrievalCircuitBreaker | None = DEFAULT_PREDICT_CIRCUIT_BREAKER,
    search_func: SearchFunc = search,
) -> PredictOutcome:
    """Retrieve top-k candidates, then let an LLM rerank among them.

    `program` overrides the real DSPy program construction, and
    `search_func` overrides `rag.retrieval.search` itself — both used by
    tests to run this fully offline, without a live Ollama instance or the
    real embedding-model-backed retrieval index.
    """

    results = search_func(amharic_property, target_class=target_class, limit=top_k)
    scored = [result for result in results if isinstance(result, SearchResult)]
    if not scored:
        return NoCandidatesFound(query=amharic_property)

    candidates = [result.property for result in scored]
    top_result = scored[0]

    if circuit_breaker is not None and not circuit_breaker.allow_request():
        log_event(LOGGER, "predict.circuit_open")
        return PredictionResult(
            property=top_result.property,
            used_llm=False,
            candidates=candidates,
            top_retrieval_result=top_result,
            reason="LLM reranking temporarily unavailable",
        )

    try:
        resolved_program = program if program is not None else _build_dspy_program()
        chosen = _call_dspy(resolved_program, amharic_property, candidates, model_alias)
    except Exception as exc:
        if circuit_breaker is not None:
            circuit_breaker.record_failure()
        log_event(LOGGER, "predict.llm_unavailable", error=exc.__class__.__name__)
        return PredictionResult(
            property=top_result.property,
            used_llm=False,
            candidates=candidates,
            top_retrieval_result=top_result,
            reason=f"LLM reranking unavailable: {exc.__class__.__name__}",
        )

    if circuit_breaker is not None:
        circuit_breaker.record_success()
    log_event(LOGGER, "predict.llm_reranked", model=model_alias)
    return PredictionResult(
        property=chosen, used_llm=True, candidates=candidates, top_retrieval_result=top_result
    )
