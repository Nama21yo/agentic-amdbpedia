from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_scaffold_paths_exist() -> None:
    required_paths = [
        "README.md",
        "docker-compose.yml",
        "pyproject.toml",
        "data",
        "rag/__init__.py",
        "rag/indexing.py",
        "rag/retrieval.py",
        "mcp_server/__init__.py",
        "mcp_server/server.py",
        "mcp_server/agent.py",
        "evaluation/test_queries.json",
        "evaluation/results.md",
        "examples/demo.md",
    ]
    missing = [path for path in required_paths if not (PROJECT_ROOT / path).exists()]
    assert missing == []


def test_packages_import() -> None:
    import mcp_server
    import rag

    assert rag.__doc__
    assert mcp_server.__doc__
