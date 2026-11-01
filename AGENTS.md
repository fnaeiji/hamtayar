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
