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
    assert Path(server["command"]).name == "uv"
    assert server["args"][:10] == [
        "run",
        "--frozen",
        "--no-dev",
        "--python",
        "3.11",
        "--directory",
        str(PROJECT_ROOT),
        "--project",
        str(PROJECT_ROOT),
        "python",
    ]
    assert Path(server["args"][10]).exists()
    assert server["env"] == {}
    assert "GROQ_API_KEY" not in server["env"]
    assert "QDRANT_URL" not in server["env"]


def test_print_desktop_config_uses_project_for_claude_working_directory() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/print_desktop_config.py"],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    server = json.loads(result.stdout)["mcpServers"]["dbpedia_mapper"]
    probe_args = [
        server["args"][0],
        "--no-sync",
        *server["args"][1:-1],
        "-c",
        "from pathlib import Path; print(Path.cwd())",
    ]

    result = subprocess.run(
        [server["command"], *probe_args],
        cwd="/tmp",
        check=True,
        text=True,
        capture_output=True,
    )

    assert Path(result.stdout.strip()) == PROJECT_ROOT


def test_runtime_just_recipes_use_frozen_python_311_without_dev_dependencies() -> None:
    justfile = (PROJECT_ROOT / "justfile").read_text(encoding="utf-8")

    runtime_command = "uv run --frozen --no-dev --python 3.11 python"
    assert f"{runtime_command} scripts/wait_for_qdrant.py" in justfile
    assert f"{runtime_command} mcp_server/server.py" in justfile
    assert f"{runtime_command} scripts/validate_corpus.py data" in justfile
