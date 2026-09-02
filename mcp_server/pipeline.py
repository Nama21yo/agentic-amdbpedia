"""Infobox extraction, ported from `agentic-dbpedia`'s `DumpTemplateParser`
(refs implementation.md 16.1).

`agentic-dbpedia`'s original parses a whole MediaWiki XML dump, streaming
`<page>` elements. Nothing here does that — the actual use case is a user
pasting one infobox's wikitext directly (`frontend/src/lib/api.ts::previewMapping`
takes a plain string, not a dump path) — so only the wikitext-level parsing
core is ported: `mwparserfromhell` when available, with the same
conservative brace-depth-aware fallback parser `agentic-dbpedia` uses when
it isn't, so behavior matches even on a host without the real parser.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from logging_config import log_event

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


def extract_infobox(wikitext: str) -> list[TemplateField]:
    """Extract the fields of the first infobox-like template found in
    `wikitext`. Returns an empty list if none is found — never raises just
    because the input isn't a recognizable infobox."""

    infobox_templates = [t for t in parse_templates(wikitext) if _is_infobox_like(t.name)]
    if not infobox_templates:
        log_event(LOGGER, "pipeline.no_infobox_found")
        return []

    log_event(LOGGER, "pipeline.infobox_extracted", template_name=infobox_templates[0].name)
    return infobox_templates[0].fields
