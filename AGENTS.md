# Hamtayar — Architecture

## 1. Responsibilities

| Path | Responsibility |
|---|---|
| `apps/ingestion` | Content intake API (`api.py`), independent worker (`worker.py`), flow coordination (`coordinator.py`), LangGraph state/steps/graph definitions (`flows.py`). |
| `apps/retrieve` | Evidence retrieval without any LLM (`retrieval.py`); LLM answering on top of retrieval (`answer.py`); model client contract (`llm.py`); HTTP entry (`api.py`). |
| `packages/core` | Shared models (`models.py`), request/result contracts (`contracts.py`), source catalog and versions (`catalog.py`), index generation lifecycle (`generations.py`), job state and queue (`jobs.py`), request scope + Padin binding (`scope.py`), storage contracts (`storage.py`), shared embedding (`embedding.py`), provider bindings (`providers.py`). |
| `packages/doc` | Format detection and extractor selection (`detect.py`), extraction contract (`contracts.py`) and implementations (`extractors.py`), structure and location preservation (`structure.py`), configurable normalization (`normalize.py`), chunking (`chunking.py`), index preparation and writing (`index.py`). |
| `packages/code` | Repository preparation and versioning (`prepare.py`), symbol/relation extraction and Hamtayar-owned indexing (`extract.py`), tool-owned indexing (`backend.py`), chunking (`chunking.py`), index writing (`index.py`), search (`search.py`), symbol context and graph neighbourhood (`context.py`), small tool contracts (`contracts.py`), CGC connector skeleton (`cgc.py`), connector registry and future slots (`registry.py`). |
| `infra/dockerize` | Packaging locations for API, worker and code tool. |
| `infra/db-init` | Database migration location. |
| `test` | `unit`, `contract`, `integration`, `security`. |

## 2. Dependency direction

```
apps/*  ->  packages/*
packages/doc   ->  packages/core
packages/code  ->  packages/core
```

- `packages/core` imports nothing from `doc`, `code` or `apps`.
- `doc` and `code` never import each other's internals; a shared need moves to `core`.
- `apps/*` never import another app's code.
- Retrieval (`apps/retrieve/retrieval.py`) does not touch `answer.py` or `llm.py`.
- Third-party SDK types stay inside adapters (`core/storage.py` stores, `code/cgc.py`, `apps/retrieve/llm.py`).
- Licensing rules, publication rules and job state live once: `core/scope.py`, `core/generations.py`, `core/jobs.py`.

## 3. Path of content and retrieval

Content in:
`apps/ingestion/api.py` -> `core/jobs.py` (job created) -> queue -> `apps/ingestion/worker.py` -> `apps/ingestion/coordinator.py` -> `packages/doc` or `packages/code` -> `core/generations.py` (generation opened, chunks written) -> validate -> publish generation.

Retrieval out:
`apps/retrieve/api.py` -> `core/scope.py` (Padin scope) -> `retrieval.py` -> `packages/core/storage.py` (vector search) -> `RetrievedContext`.
Answering: `answer.py` -> `retrieval.py` context -> `llm.py` contract -> citations.

## 4. Where to change

| Change | Location |
|---|---|
| New OCR engine | `packages/doc/extractors.py` (a `DocumentExtractor` implementation) + registration in `packages/doc/detect.py`; `packages/doc/contracts.py` stays unchanged. |
| New code tool provider | `packages/code/registry.py` (`CONNECTORS` slot + `ConnectorFactory`), implementation in `packages/code/cgc.py` style; choose `CodeToolMode.EXTRACTION` (`extract.py`) or `BACKEND` (`backend.py`). |
| New language model | `apps/retrieve/llm.py` (implementation of `LanguageModelPort`); `retrieval.py` and everything under `packages/` are untouched. |

## 5. Pipeline monitoring

Information for agents: this project runs **runtime pipelines** (LangGraph workflows), not CI-only logic. Monitoring means observing those graphs while they execute. The files named below are empty placeholders as of the structure created on 2026-11-01; the rules apply once they are implemented.

Pipelines and their graphs:

| Pipeline | Graph entry | Nodes, in order |
|---|---|---|
| Document ingestion | `apps/document_ingestion/workflows/document_ingestion/graph.py` | `load_document` -> `parse` -> `normalize` -> `chunk` -> `embed` -> `index` -> `activate` |
| Answer | `apps/retrieval/workflows/answer/graph.py` | `prefilter` -> `normalize_query` -> `retrieve` -> `rerank` -> `reauthorize` -> `build_context` -> `generate_answer` |

Monitoring has exactly four choke points. Change these; do not instrument a node:

| Concern | Location |
|---|---|
| Metrics, tracing, log shape and correlation ids | `apps/core/observability.py` |
| Per-step transitions, checkpoints, resume after failure | `apps/orchestration/checkpointer.py` |
| Graph invocation, step budget, error propagation | `apps/orchestration/execution.py` |
| Queue consumption, retry, dead-letter, dispatch to a workflow | `apps/worker/consumer.py`, `apps/worker/dispatcher.py` |
| The state each step reads and writes | `apps/*/workflows/*/state.py` |

Rules:

- A node returns state; it does not log, emit metrics, or swallow exceptions. One choke point produces one log/metric shape instead of seven.
- Every step transition is recorded once in the checkpointer, so an interrupted run is identifiable and resumable; do not record transitions in HTTP handlers or nodes.
- A failure surfaces as an error carrying the shared `ErrorCode` vocabulary (`packages/contracts`), not an ad-hoc string.
- Monitoring is read-only with respect to business state: observing a step never changes what that step decides.
- No monitoring SDK type (metrics, tracing, queue client) is imported outside its adapter in `apps/core/observability.py`; nodes and API modules stay free of third-party observability types.
- Adding a node means adding it to `state.py`, to the graph, and to the step vocabulary in one place — never a new monitoring hook per node.
