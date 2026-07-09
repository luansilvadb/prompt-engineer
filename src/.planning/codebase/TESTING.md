# TESTING.md

**Date:** 2026-07-09
**Scope:** Full Repo

## Framework
- No standard unit testing framework (like `pytest`) is immediately visible in the root or a dedicated `tests/` directory.

## Core Validation
- System relies heavily on LLM-based evaluation and regression testing.
- `drift_monitor.py` acts as a continuous test suite for the model, comparing the LLM's output against a `golden_set.json` (Golden Set).
- Uses metrics like Spearman rank correlation and Mean Absolute Error (MAE) to validate that prompt changes improve outcomes and don't introduce regressions.

## Continuous Integration
- CI config is not present in the immediate structure. Evaluators run as part of the application logic.
