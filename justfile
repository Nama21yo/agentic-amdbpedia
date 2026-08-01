set dotenv-load := true

export UV_CACHE_DIR := env_var_or_default("UV_CACHE_DIR", ".uv-cache")
export UV_TOOL_DIR := env_var_or_default("UV_TOOL_DIR", ".uv-tools")

lint:
    uvx ruff check .
    uvx ruff format --check .
    uvx --python 3.11 --with pydantic --with pydantic-settings --with pytest --with hypothesis --with 'mcp[cli]==1.28.0' --with groq mypy config.py errors.py logging_config.py rag mcp_server scripts tests

test:
    uvx --python 3.11 --with pydantic --with pydantic-settings --with pytest --with pytest-asyncio --with hypothesis --with 'mcp[cli]==1.28.0' --with groq --with qdrant-client pytest -m "not integration and not e2e and not perf"

test-integration:
    uv run python scripts/wait_for_qdrant.py
    uvx --python 3.11 --with pydantic --with pydantic-settings --with pytest --with pytest-asyncio --with hypothesis --with 'mcp[cli]==1.28.0' --with groq --with qdrant-client pytest -m integration

test-e2e:
    uv run python scripts/wait_for_qdrant.py
    uvx --python 3.11 --with pydantic --with pydantic-settings --with pytest --with pytest-asyncio --with hypothesis --with 'mcp[cli]==1.28.0' --with groq --with qdrant-client pytest -m e2e

test-perf:
    uvx --python 3.11 --with pydantic --with pydantic-settings --with pytest --with pytest-asyncio --with pytest-benchmark --with hypothesis --with 'mcp[cli]==1.28.0' --with groq --with qdrant-client pytest -m perf

coverage-indexing:
    uvx --with pydantic --with pydantic-settings --with pytest --with pytest-cov --with qdrant-client pytest tests/test_indexing.py --cov=rag.indexing

run-server:
    uv run python mcp_server/server.py

validate-corpus:
    python scripts/validate_corpus.py data
