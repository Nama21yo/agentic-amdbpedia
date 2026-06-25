# Latency Budget Report

Benchmarks live in `tests/perf/test_latency.py` and run via `just test-perf`.
They are scheduled/manual CI checks rather than pull-request gates to avoid flaky
latency failures on shared runners.

| Path | Target p95 | Alert threshold | Test |
|---|---:|---:|---|
| Qdrant hybrid retrieval | < 200ms | 400ms | `tests/perf/test_latency.py::test_qdrant_hybrid_query_latency_budget` |
| Groq fast-path classification | < 1s | 2s | `tests/perf/test_latency.py::test_fast_path_classification_latency_budget` |
| Full ReAct happy path | < 4s | 8s | `tests/perf/test_latency.py::test_react_happy_path_latency_budget` |

The checked tests assert the 2x alert threshold. The report intentionally avoids
recording machine-specific measurements as fixed truth.
