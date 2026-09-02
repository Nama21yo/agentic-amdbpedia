"""Infobox extraction and pipeline orchestration (refs implementation.md
16.1/16.2).

**16.1 — extraction**: ported from `agentic-dbpedia`'s `DumpTemplateParser`.
`agentic-dbpedia`'s original parses a whole MediaWiki XML dump, streaming
`<page>` elements. Nothing here does that — the actual use case is a user
pasting one infobox's wikitext directly (`frontend/src/lib/api.ts::previewMapping`
takes a plain string, not a dump path) — so only the wikitext-level parsing
core is ported: `mwparserfromhell` when available, with the same
conservative brace-depth-aware fallback parser `agentic-dbpedia` uses when
it isn't, so behavior matches even on a host without the real parser.

**16.2 — orchestration**: ported from `agentic-dbpedia`'s 4-node
`MappingAgentState` graph shape (`week3_extract_parameters ->
week4_match_properties -> week5_format_syntax -> week6_validate_and_persist`),
wired to this repo's own pieces instead of `agentic-dbpedia`'s: 16.1's
`extract_first_infobox`, 11's `rag.predict.predict_property`, the existing
`generate_mapping_syntax_impl`/`build_mapping_wikitext`, and 14.1's
`create_review_item`. Same optional-`langgraph`-with-sequential-fallback
pattern as the original; the persist node is genuinely async (this repo's
DB layer is async SQLAlchemy throughout), and LangGraph's own `ainvoke()`
runs sync and async nodes together in one graph without any special
handling — verified directly before relying on it.
"""

from __future__ import annotations

import importlib
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, TypedDict, cast

from sqlalchemy.ext.asyncio import AsyncSession

from db.session import create_review_item
from logging_config import log_event
from mcp_server.publish import build_mapping_wikitext
from mcp_server.server import MappingEntry, MappingPayload, generate_mapping_syntax_impl
from rag.ontology import AmharicMappingIndex
from rag.predict import PredictionResult, predict_property

LOGGER = logging.getLogger("dbpedia_mapping_assistant.pipeline")

INFOBOX_MARKERS = ("infobox", "info box", "መረጃ", "ሳጥን")


@dataclass(frozen=True, slots=True)
class TemplateField:
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class ExtractedTemplate:
    name: str
    fields: list[TemplateField]


def _is_infobox_like(template_name: str) -> bool:
    normalized = template_name.replace("_", " ").casefold()
    return any(marker in normalized for marker in INFOBOX_MARKERS)


def _split_top_level(body: str) -> list[str]:
    """Split a template body on top-level `|` only — one still inside a
    nested `{{...}}` doesn't count. Mirrors agentic-dbpedia's own fallback
    parser exactly, since the two must agree on edge cases."""

    parts: list[str] = []
    depth = 0
    start = 0
    index = 0

    while index < len(body):
        pair = body[index : index + 2]
        if pair == "{{":
            depth += 1
            index += 2
            continue
        if pair == "}}" and depth:
            depth -= 1
            index += 2
            continue
        if body[index] == "|" and depth == 0:
            parts.append(body[start:index])
            start = index + 1
        index += 1

    parts.append(body[start:])
    return parts


def _extract_top_level_template_bodies(text: str) -> list[str]:
    bodies: list[str] = []
    index = 0
    while True:
        open_index = text.find("{{", index)
        if open_index == -1:
            break
        depth = 1
        cursor = open_index + 2
        while cursor < len(text) and depth:
            pair = text[cursor : cursor + 2]
            if pair == "{{":
                depth += 1
                cursor += 2
                continue
            if pair == "}}":
                depth -= 1
                cursor += 2
                continue
            cursor += 1
        bodies.append(text[open_index + 2 : cursor - 2])
        index = cursor
    return bodies


def _parse_with_fallback(text: str) -> list[ExtractedTemplate]:
    templates: list[ExtractedTemplate] = []

    for body in _extract_top_level_template_bodies(text):
        parts = _split_top_level(body)
        if not parts:
            continue

        template_name = parts[0].strip()
        fields: list[TemplateField] = []

        for raw_part in parts[1:]:
            if "=" not in raw_part:
                continue
            name, value = raw_part.split("=", 1)
            name = name.strip()
            if not name or name.isdecimal():
                continue
            fields.append(TemplateField(name=name, value=value.strip()))

        if template_name and fields:
            templates.append(ExtractedTemplate(name=template_name, fields=fields))

    return templates


def _parse_with_mwparser(text: str) -> list[ExtractedTemplate]:
    import mwparserfromhell

    wikicode = mwparserfromhell.parse(text)
    templates: list[ExtractedTemplate] = []

    for raw_template in wikicode.filter_templates(recursive=False):
        template_name = str(raw_template.name).strip()
        fields: list[TemplateField] = []

        for raw_param in raw_template.params:
            name = str(raw_param.name).strip()
            if not name or name.isdecimal():
                continue
            fields.append(TemplateField(name=name, value=str(raw_param.value).strip()))

        if fields:
            templates.append(ExtractedTemplate(name=template_name, fields=fields))

    return templates


def parse_templates(text: str) -> list[ExtractedTemplate]:
    """Parse every template in `text`, using `mwparserfromhell` when
    installed and the conservative fallback parser otherwise — same
    fallback behavior as `agentic-dbpedia`'s own `DumpTemplateParser`."""

    try:
        templates = _parse_with_mwparser(text)
    except ModuleNotFoundError:
        log_event(LOGGER, "pipeline.parser_fallback")
        templates = _parse_with_fallback(text)
    return templates


def extract_first_infobox(wikitext: str) -> ExtractedTemplate | None:
    """The first infobox-like template found in `wikitext`, name and all —
    `extract_infobox` (16.1's original public function) only returns the
    fields, which was enough for that milestone but not for 16.2's
    orchestration, which also needs the template name itself for the
    review item and the published page title."""

    infobox_templates = [t for t in parse_templates(wikitext) if _is_infobox_like(t.name)]
    if not infobox_templates:
        log_event(LOGGER, "pipeline.no_infobox_found")
        return None

    log_event(LOGGER, "pipeline.infobox_extracted", template_name=infobox_templates[0].name)
    return infobox_templates[0]


def extract_infobox(wikitext: str) -> list[TemplateField]:
    """Extract the fields of the first infobox-like template found in
    `wikitext`. Returns an empty list if none is found — never raises just
    because the input isn't a recognizable infobox."""

    template = extract_first_infobox(wikitext)
    return template.fields if template is not None else []


try:  # pragma: no cover - exercised when the optional dependency is installed.
    _langgraph_graph = importlib.import_module("langgraph.graph")
except ModuleNotFoundError:  # pragma: no cover - fallback is covered in local tests.
    END = "__end__"
    StateGraph: Any | None = None
else:  # pragma: no cover - depends on optional dependency availability.
    END = _langgraph_graph.END
    StateGraph = _langgraph_graph.StateGraph


class PipelineState(TypedDict, total=False):
    wikitext: str
    domain_class: str
    run_id: str
    session: AsyncSession
    mapping_index: AmharicMappingIndex
    template_name: str
    fields: list[TemplateField]
    predictions: dict[str, PredictionResult]
    mappings: list[dict[str, Any]]
    mapping_wikitext: str
    xml_rules: str
    review_item_id: str | None
    warnings: list[str]


def _extract_node(state: PipelineState) -> dict[str, Any]:
    template = extract_first_infobox(state["wikitext"])
    warnings = list(state.get("warnings", []))

    if template is None:
        warnings.append("No infobox-like template found in the given wikitext.")
        return {"template_name": "", "fields": [], "warnings": warnings}

    state_mapping_index = state.get("mapping_index")
    mapping_index = (
        state_mapping_index
        if state_mapping_index is not None
        else AmharicMappingIndex.from_default_cache()
    )
    kept_fields: list[TemplateField] = []
    skipped = 0
    for field in template.fields:
        if mapping_index.lookup(field.name) is not None:
            skipped += 1
            continue
        kept_fields.append(field)

    if skipped:
        warnings.append(
            f"Skipped {skipped} field(s) already present in the published Amharic mappings."
        )
    if not kept_fields:
        warnings.append("No unmapped fields remained after filtering already-published mappings.")

    return {"template_name": template.name, "fields": kept_fields, "warnings": warnings}


def _predict_node(state: PipelineState) -> dict[str, Any]:
    domain_class = state.get("domain_class")
    predictions: dict[str, PredictionResult] = {}
    warnings = list(state.get("warnings", []))

    for field in state.get("fields", []):
        outcome = predict_property(field.name, target_class=domain_class)
        if isinstance(outcome, PredictionResult):
            predictions[field.name] = outcome
        else:
            warnings.append(f"No retrieval candidates found for {field.name!r}.")

    return {"predictions": predictions, "warnings": warnings}


def _format_node(state: PipelineState) -> dict[str, Any]:
    domain_class = state.get("domain_class") or "Thing"
    predictions = state.get("predictions", {})
    warnings = list(state.get("warnings", []))

    mappings: list[dict[str, Any]] = [
        {
            "templateProperty": name,
            "ontologyProperty": prediction.property,
            "confidence": (
                prediction.top_retrieval_result.score if prediction.top_retrieval_result else 0.0
            ),
        }
        for name, prediction in predictions.items()
    ]

    if not mappings:
        warnings.append("No mappings were predicted; nothing to format.")
        return {"mappings": [], "mapping_wikitext": "", "xml_rules": "", "warnings": warnings}

    try:
        payload = MappingPayload(
            domain_class=domain_class,
            mappings=[
                MappingEntry(
                    templateProperty=mapping["templateProperty"],
                    ontologyProperty=mapping["ontologyProperty"],
                )
                for mapping in mappings
            ],
        )
        xml_rules = generate_mapping_syntax_impl(payload)
    except Exception as exc:
        warnings.append(f"Could not generate deterministic XML: {exc.__class__.__name__}")
        xml_rules = ""

    mapping_wikitext = build_mapping_wikitext(domain_class, mappings)

    return {
        "mappings": mappings,
        "mapping_wikitext": mapping_wikitext,
        "xml_rules": xml_rules,
        "warnings": warnings,
    }


async def _persist_node(state: PipelineState) -> dict[str, Any]:
    mappings = state.get("mappings", [])
    if not mappings:
        return {"review_item_id": None}

    session = state["session"]
    item = await create_review_item(
        session,
        run_id=state.get("run_id", ""),
        template_name=state.get("template_name", ""),
        domain_class=state.get("domain_class") or "Thing",
        mappings=mappings,
    )
    log_event(LOGGER, "pipeline.review_item_created", review_id=item.id)
    return {"review_item_id": item.id}


PipelineNode = Callable[[PipelineState], dict[str, Any] | Awaitable[dict[str, Any]]]


class _SequentialPipelineGraph:
    """Async-aware sequential fallback for when `langgraph` isn't
    installed — same shape as `agentic-dbpedia`'s own
    `_SequentialMappingAgentGraph`, extended to await async nodes too
    (this pipeline's persist step genuinely needs one)."""

    def __init__(self, nodes: Sequence[PipelineNode]) -> None:
        self._nodes = nodes

    async def ainvoke(self, initial_state: PipelineState) -> PipelineState:
        state: dict[str, Any] = dict(initial_state)
        for node in self._nodes:
            updates = node(cast(PipelineState, state))
            if isinstance(updates, Awaitable):
                updates = await updates
            state.update(updates)
        return cast(PipelineState, state)


def _build_graph() -> Any:
    nodes: list[PipelineNode] = [_extract_node, _predict_node, _format_node, _persist_node]
    if StateGraph is None:
        return _SequentialPipelineGraph(nodes)

    workflow = StateGraph(PipelineState)
    workflow.add_node("extract_infobox_fields", _extract_node)
    workflow.add_node("predict_properties", _predict_node)
    workflow.add_node("format_mapping_syntax", _format_node)
    workflow.add_node("persist_review_item", _persist_node)
    workflow.set_entry_point("extract_infobox_fields")
    workflow.add_edge("extract_infobox_fields", "predict_properties")
    workflow.add_edge("predict_properties", "format_mapping_syntax")
    workflow.add_edge("format_mapping_syntax", "persist_review_item")
    workflow.add_edge("persist_review_item", END)
    return workflow.compile()


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    template_name: str
    domain_class: str
    mappings: list[dict[str, Any]]
    mapping_wikitext: str
    xml_rules: str
    warnings: list[str]
    review_item_id: str | None


async def run_mapping_pipeline(
    wikitext: str,
    *,
    domain_class: str,
    session: AsyncSession,
    run_id: str | None = None,
    mapping_index: AmharicMappingIndex | None = None,
) -> PipelineResult:
    """Extract -> predict -> format -> persist, end to end.

    Ported from `agentic-dbpedia`'s 4-node `week3_extract_parameters ->
    week4_match_properties -> week5_format_syntax ->
    week6_validate_and_persist` graph shape, wired to this repo's own
    pieces. `session` is a live `AsyncSession` (14.1) the caller already
    holds — this function never opens or closes one itself, matching how
    `mcp_server/http_app.py`'s route handlers already manage sessions.
    """

    resolved_run_id = run_id or str(uuid.uuid4())
    initial_state: PipelineState = {
        "wikitext": wikitext,
        "domain_class": domain_class,
        "run_id": resolved_run_id,
        "session": session,
        # `mapping_index or ...` would be wrong here: AmharicMappingIndex
        # defines __len__, so a deliberately empty (but valid) index is
        # falsy and would get silently replaced by the default cache.
        "mapping_index": (
            mapping_index if mapping_index is not None else AmharicMappingIndex.from_default_cache()
        ),
        "warnings": [],
    }

    graph = _build_graph()
    final_state = await graph.ainvoke(initial_state)

    log_event(
        LOGGER,
        "pipeline.completed",
        run_id=resolved_run_id,
        mapping_count=len(final_state.get("mappings", [])),
    )

    return PipelineResult(
        run_id=resolved_run_id,
        template_name=final_state.get("template_name", ""),
        domain_class=domain_class,
        mappings=final_state.get("mappings", []),
        mapping_wikitext=final_state.get("mapping_wikitext", ""),
        xml_rules=final_state.get("xml_rules", ""),
        warnings=final_state.get("warnings", []),
        review_item_id=final_state.get("review_item_id"),
    )
