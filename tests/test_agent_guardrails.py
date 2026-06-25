from __future__ import annotations

import json
from typing import Any

from mcp_server.agent import ReasoningStep, ToolRequest, run_mapping_agent


class ScriptedGroq:
    def __init__(self, steps: list[ReasoningStep]) -> None:
        self.steps = steps
        self.index = 0

    def reason(
        self, _messages: list[dict[str, Any]], _tools: list[dict[str, Any]]
    ) -> ReasoningStep:
        step = self.steps[self.index]
        self.index += 1
        return step


def test_injected_instructions_never_alter_generate_mapping_arguments() -> None:
    groq = ScriptedGroq(
        [
            ReasoningStep(tool_call=ToolRequest("find_semantic_match", {"amharic_property": "x"})),
            ReasoningStep(
                tool_call=ToolRequest(
                    "generate_mapping_syntax",
                    {
                        "domain_class": "Airport",
                        "mappings": [
                            {"templateProperty": "x", "ontologyProperty": "attackerProperty"}
                        ],
                    },
                )
            ),
            ReasoningStep(content="done", final=True),
        ]
    )

    observed_property = ""

    def runner(request: ToolRequest) -> str:
        nonlocal observed_property
        if request.name == "find_semantic_match":
            return json.dumps(
                {
                    "status": "ok",
                    "matches": [{"property": "icaoLocationIdentifier", "class": "Airport"}],
                }
            )
        observed_property = request.arguments["mappings"][0]["ontologyProperty"]
        return "<TemplateMapping />"

    run_mapping_agent("አይካኦ_ኮድ", groq_client=groq, tool_runner=runner)

    assert observed_property == "icaoLocationIdentifier"


def test_agent_never_emits_raw_xml_not_from_tool() -> None:
    groq = ScriptedGroq(
        [ReasoningStep(content="<TemplateMapping>bad</TemplateMapping>", final=True)]
    )

    response = run_mapping_agent("አይካኦ_ኮድ", groq_client=groq)

    assert (
        response.final_answer
        == "I cannot provide raw XML directly; use the generated mapping tool output."
    )


def test_no_match_final_answer_never_guesses_property_name() -> None:
    groq = ScriptedGroq(
        [ReasoningStep(tool_call=ToolRequest("find_semantic_match", {"amharic_property": "x"}))]
    )

    response = run_mapping_agent(
        "ያልታወቀ",
        groq_client=groq,
        tool_runner=lambda _request: json.dumps({"status": "no_match", "matches": []}),
    )

    assert "No confident DBpedia ontology match" in response.final_answer
    assert "icaoLocationIdentifier" not in response.final_answer
