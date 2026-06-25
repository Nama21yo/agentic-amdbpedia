"""Print Claude Desktop MCP configuration for this checkout."""

from __future__ import annotations

import json
from pathlib import Path


def build_desktop_config(project_root: Path | None = None) -> dict[str, object]:
    root = project_root or Path(__file__).resolve().parents[1]
    server_path = root / "mcp_server" / "server.py"
    return {
        "mcpServers": {
            "dbpedia_mapper": {
                "command": "uv",
                "args": ["run", "--project", str(root), "python", str(server_path)],
                "env": {"GROQ_API_KEY": "your_groq_api_key_here"},
            }
        }
    }


def main() -> int:
    print(json.dumps(build_desktop_config(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
