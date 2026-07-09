# ARCHITECTURE.md

**Date:** 2026-07-09
**Scope:** Full Repo

## Pattern
- Monolithic API server with specialized ML/Prompt Optimization backend.
- Local JSON-based persistence instead of a database.

## Layers
1. **Entry Point / API Layer**: `api.py` and `routers/` (FastAPI). Exposes jobs and frontend routes.
2. **Core Logic / Optimizer**: `teleprompter.py` (MCTS Prompt Optimizer), `optimizer.py`, `mutations.py` (prompt variations).
3. **Verification / Drift**: `drift_monitor.py` (Gatekeeper that measures model degradation using a Golden Set of probes).
4. **Data Layer**: `experience_store.py`, `store.py`, writing to `outputs/` directory.

## Data Flow
- User submits a job via FastAPI (`routers/jobs.py`).
- The job triggers prompt optimization (`teleprompter.py` / `optimizer.py`).
- The LLM interacts via DSPy (`config.py`).
- Results and models are evaluated against a Golden Set (`drift_monitor.py`) to prevent regressions.
- Approved models and experiences are persisted to disk (`outputs/`).

## Entry Points
- `api.py`: FastAPI application serving the API and static frontend assets.
