from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_desktop_handshake_schema_matches_documented_tools() -> None:
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
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        resources = {str(resource.uri) for resource in (await session.list_resources()).resources}

    assert set(tools) == {"find_semantic_match", "generate_mapping_syntax"}
    find_schema = tools["find_semantic_match"].inputSchema
    assert find_schema["required"] == ["amharic_property"]
    assert set(find_schema["properties"]) == {"amharic_property", "target_class"}

    xml_schema = tools["generate_mapping_syntax"].inputSchema
    assert xml_schema["required"] == ["payload"]
    assert "payload" in xml_schema["properties"]
    assert resources == {"resources://benchmarks/latest"}
