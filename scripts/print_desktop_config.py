"""Print Claude Desktop MCP configuration for this checkout."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def build_desktop_config(project_root: Path | None = None) -> dict[str, object]:
    root = project_root or Path(__file__).resolve().parents[1]
    server_path = root / "mcp_server" / "server.py"
    uv_command = shutil.which("uv") or "uv"
    return {
        "mcpServers": {
            "dbpedia_mapper": {
                "command": uv_command,
                "args": [
                    "run",
                    "--frozen",
                    "--no-dev",
                    "--python",
                    "3.11",
                    "--directory",
                    str(root),
                    "--project",
                    str(root),
                    "python",
                    str(server_path),
                ],
                "env": {},
            }
        }
    }


def main() -> int:
    print(json.dumps(build_desktop_config(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
