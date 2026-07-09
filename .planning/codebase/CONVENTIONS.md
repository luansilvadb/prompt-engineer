# CONVENTIONS.md

**Date:** 2026-07-09
**Scope:** Full Repo

## Code Style
- Standard PEP8 style guidelines.
- Python type hints used extensively (e.g., `List`, `Optional`, `dict`, `float`).

## Patterns
- **DSPy**: DSPy Signatures are defined centrally (`signatures.py`) and used inside predictive models.
- **Config as Code**: Hyperparameters are dynamically loaded from env vars but have sensible hardcoded defaults (`config.py`).
- **Immutability**: Golden datasets are explicitly treated as read-only at runtime. Offline curation is strictly enforced (`drift_monitor.py`).

## Error Handling
- Domain-specific exceptions are used (e.g., `DriftMeasurementError`).
- Resilient fallback logic when files are missing (e.g. falling back to bundled data if frozen).
