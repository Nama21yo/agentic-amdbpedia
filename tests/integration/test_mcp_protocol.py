from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_mcp_protocol_lists_tools_calls_tool_and_reads_resource() -> None:
    env = os.environ.copy()
    env["MCP_SERVER_SKIP_STARTUP_CHECKS"] = "1"
    env["MCP_SERVER_TEST_MODE"] = "1"
    env["GROQ_API_KEY"] = "gsk_test_placeholder"
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    async with (
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        tool_names = {tool.name for tool in tools.tools}
        assert {"find_semantic_match", "generate_mapping_syntax"} <= tool_names

        match = await session.call_tool(
            "find_semantic_match",
            {"amharic_property": "አይካኦ_ኮድ", "target_class": "Airport"},
        )
        match_payload = json.loads(cast(Any, match.content[0]).text)
        assert match_payload["status"] == "ok"

        xml = await session.call_tool(
            "generate_mapping_syntax",
            {
                "payload": {
                    "domain_class": "Airport",
                    "mappings": [
                        {
                            "templateProperty": "አይካኦ_ኮድ",
                            "ontologyProperty": "icaoLocationIdentifier",
                        }
                    ],
                }
            },
        )
        assert "TemplateMapping" in cast(Any, xml.content[0]).text

        resources = await session.list_resources()
        assert "resources://benchmarks/latest" in {
            str(resource.uri) for resource in resources.resources
        }
        metrics = await session.read_resource(cast(Any, "resources://benchmarks/latest"))
        metrics_payload = json.loads(cast(Any, metrics.contents[0]).text)
        assert metrics_payload["status"] == "no_evaluation_run_yet"
