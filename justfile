set dotenv-load := true

export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", ".uv-cache")
export UV_TOOL_DIR := env_var_or_default("UV_TOOL_DIR", ".uv-tools")

lint:
    uvx ruff check .
    uvx ruff format --check .
    uv run --frozen --python 3.11 mypy config.py errors.py logging_config.py db rag mcp_server scripts tests

test:
    uv run --frozen --python 3.11 pytest -m "not integration and not e2e and not perf"

test-integration:
    uv run --frozen --python 3.11 pytest -m integration

test-e2e:
    uv run --frozen --python 3.11 pytest -m e2e

test-perf:
    uv run --frozen --python 3.11 pytest -m perf

run-server:
    uv run --frozen --no-dev --python 3.11 python mcp_server/server.py

validate-corpus:
    uv run --frozen --no-dev --python 3.11 python scripts/validate_corpus.py data

refresh-ontology:
    uv run --frozen --no-dev --python 3.11 python scripts/refresh_wiki_cache.py --target ontology

refresh-mappings:
    uv run --frozen --no-dev --python 3.11 python scripts/refresh_wiki_cache.py --target mappings
