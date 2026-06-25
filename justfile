set dotenv-load := false

export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", ".uv-cache")
export UV_TOOL_DIR := env_var_or_default("UV_TOOL_DIR", ".uv-tools")

lint:
    uvx ruff check .
    uvx ruff format --check .
    uvx --with pydantic --with pydantic-settings --with pytest --with hypothesis --with 'mcp[cli]' --with groq mypy config.py rag mcp_server scripts tests

test:
    uvx --with pydantic --with pydantic-settings --with pytest --with pytest-asyncio --with hypothesis --with 'mcp[cli]' --with groq --with qdrant-client pytest -m "not integration and not e2e"

test-integration:
    python scripts/wait_for_qdrant.py
    uvx --with pydantic --with pydantic-settings --with pytest --with pytest-asyncio --with hypothesis --with 'mcp[cli]' --with groq --with qdrant-client pytest -m integration

coverage-indexing:
    uvx --with pydantic --with pydantic-settings --with pytest --with pytest-cov --with qdrant-client pytest tests/test_indexing.py --cov=rag.indexing

run-server:
    uv run python mcp_server/server.py

validate-corpus:
    python scripts/validate_corpus.py data
