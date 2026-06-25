UV_CACHE_DIR ?= .uv-cache
UV_TOOL_DIR ?= .uv-tools
export UV_CACHE_DIR
export UV_TOOL_DIR

.PHONY: lint test test-integration run-server validate-corpus

lint:
	uvx ruff check .
	uvx ruff format --check .
	uvx --with pydantic --with pydantic-settings --with pytest mypy config.py rag mcp_server scripts tests

test:
	uvx --with pydantic --with pydantic-settings --with pytest pytest -m "not integration and not e2e"

test-integration:
	python scripts/wait_for_qdrant.py
	uvx --with pydantic --with pydantic-settings --with pytest pytest -m integration

run-server:
	uv run python mcp_server/server.py

validate-corpus:
	python scripts/validate_corpus.py data
