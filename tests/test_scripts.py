from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_print_desktop_config_outputs_valid_json_with_existing_path() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/print_desktop_config.py"],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    server = payload["mcpServers"]["dbpedia_mapper"]
    assert server["command"] == "uv"
    assert server["args"][:4] == ["run", "--project", str(PROJECT_ROOT), "python"]
    assert Path(server["args"][4]).exists()
    assert "GROQ_API_KEY" in server["env"]


def test_print_desktop_config_uses_project_for_claude_working_directory() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(PROJECT_ROOT),
            "python",
            "-c",
            "from mcp.server.fastmcp import FastMCP; print('ok')",
        ],
        cwd="/tmp",
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stdout.strip() == "ok"


def test_indexing_script_direct_execution_imports_project_root() -> None:
    result = subprocess.run(
        [sys.executable, "rag/indexing.py", "--help"],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Index DBpedia ontology property documents into Qdrant" in result.stdout
