from __future__ import annotations

from mcp_server.pipeline import (
    TemplateField,
    _parse_with_fallback,
    _parse_with_mwparser,
    extract_infobox,
    parse_templates,
)

# A real Amharic Wikipedia-shaped infobox: Dedessa Bridge ("ደደሳ ድልድይ"),
# its length field ("ርዝመት") the stated 16.1 acceptance criterion.
BRIDGE_WIKITEXT = """{{መረጃሳጥን ድልድይ
| ስም = ደደሳ ድልድይ
| ርዝመት = 1,700 ሜትር
| የተከፈተበት_ቀን = 1985
}}"""


def test_extract_infobox_parses_the_bridge_example_length_field() -> None:
    fields = extract_infobox(BRIDGE_WIKITEXT)

    length_field = next(f for f in fields if f.name == "ርዝመት")
    assert length_field.value == "1,700 ሜትር"


def test_extract_infobox_returns_all_fields_in_order() -> None:
    fields = extract_infobox(BRIDGE_WIKITEXT)

    assert fields == [
        TemplateField(name="ስም", value="ደደሳ ድልድይ"),
        TemplateField(name="ርዝመት", value="1,700 ሜትር"),
        TemplateField(name="የተከፈተበት_ቀን", value="1985"),
    ]


def test_extract_infobox_returns_empty_for_a_non_infobox_template() -> None:
    fields = extract_infobox("{{Cite web | url = http://example.com | title = Something}}")

    assert fields == []


def test_extract_infobox_returns_empty_for_plain_text() -> None:
    assert extract_infobox("just some prose, no templates at all") == []


def test_extract_infobox_recognizes_english_infobox_marker() -> None:
    fields = extract_infobox("{{Infobox airport | name = Bole International Airport}}")

    assert fields == [TemplateField(name="name", value="Bole International Airport")]


def test_extract_infobox_ignores_positional_parameters() -> None:
    fields = extract_infobox("{{Infobox bridge | positional_value | ርዝመት = 500}}")

    assert fields == [TemplateField(name="ርዝመት", value="500")]


def test_extract_infobox_picks_the_first_infobox_when_multiple_templates_present() -> None:
    wikitext = "{{Cite web | url = x}} {{Infobox bridge | ርዝመት = 500}}"

    fields = extract_infobox(wikitext)

    assert fields == [TemplateField(name="ርዝመት", value="500")]


def test_parse_templates_handles_nested_templates_without_breaking_on_inner_pipes() -> None:
    wikitext = "{{Infobox bridge | ርዝመት = {{convert|500|m}} }}"

    templates = parse_templates(wikitext)

    assert len(templates) == 1
    assert templates[0].fields[0].name == "ርዝመት"
    assert templates[0].fields[0].value == "{{convert|500|m}}"


def test_mwparser_and_fallback_parsers_agree_on_the_bridge_example() -> None:
    """The fallback parser (used when mwparserfromhell isn't installed)
    must produce identical results to the real parser for the stated
    acceptance-criterion example — not just "close enough"."""

    assert _parse_with_mwparser(BRIDGE_WIKITEXT) == _parse_with_fallback(BRIDGE_WIKITEXT)
