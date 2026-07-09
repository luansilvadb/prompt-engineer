# STRUCTURE.md

**Date:** 2026-07-09
**Scope:** Full Repo

## Directory Layout
- `api.py`: FastAPI server setup.
- `routers/`: Web endpoints (`jobs.py`, `frontend.py`).
- `outputs/`: Data persistence layer.
  - `golden/`: Golden Set references (`golden_set.json`).
  - `models/`: Optimized model backups.
  - `jobs/`: Job metadata.
  - `skills/`: Output skills.
  - `strategies/`: Discovered strategies.
  - `experiences/`: Run logs (`experience_log.jsonl`).
- `drift_monitor.py`, `optimizer.py`, `teleprompter.py`, `mutations.py`, `value_estimator.py`: Core logic for LLM optimization and validation.
- `schemas.py`: Shared data models (likely Pydantic models).
- `signatures.py`: DSPy Signatures.
- `config.py`: LiteLLM and DSPy setup, environment hyperparameter loading.
- `data/`: Extraneous or input data.

## Naming Conventions
- standard snake_case for python modules and functions.
- CamelCase for Python classes (e.g. `JudgeProbeRunner`, `DriftGate`).
- Consistent `.json` or `.jsonl` for file storage.
