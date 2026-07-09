# INTEGRATIONS.md

**Date:** 2026-07-09
**Scope:** Full Repo

## External APIs
- **LLM Providers:** Configured via `config.py` using `LiteLLM`. It dynamically routes to OpenAI, Nvidia NIM, Zhipu, and others based on the `MODEL_NAME` or `MODEL_PREFIX` environment variables.

## Databases
- None currently implemented via a traditional RDBMS.
- **File System Storage:** JSON and JSONL files in `src/outputs/` act as a local datastore (`experience_store.py`, `store.py`).

## Auth Providers
- None detected. The API uses basic CORS middleware (`api.py`) with `allow_origins=['*']`.

## Webhooks
- None currently detected.
