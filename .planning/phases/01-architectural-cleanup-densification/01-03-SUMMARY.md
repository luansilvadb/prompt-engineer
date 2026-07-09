---
phase: 01-architectural-cleanup-densification
plan: 03
subsystem: drift
tags: [refactor, extraction]
requires: [01-01]
provides: [01-04]
tech-stack.added: []
key-files.created:
  - src/drift/golden.py
  - src/drift/runner.py
  - src/drift/metrics.py
key-decisions:
  - Flattened GoldenSet._load() by extracting _restore_frozen_golden and _parse_golden_json helpers.
  - Flattened medir_drift and spearman correlation into pure functions inside src/drift/metrics.py without using OO patterns.
requirements-completed: [ARC-02, ARC-03]
duration: 5 min
completed: 2026-07-09T19:18:25Z
coverage:
  - kind: verification
    ref: "python -c 'from src.drift.golden import GoldenSet, GOLDEN_DIR; g=GoldenSet(); assert hasattr(g,\"probes\"); print(\"golden ok\")'"
    status: pass
    human_judgment: false
  - kind: verification
    ref: "python -c 'from src.drift.runner import JudgeProbeRunner; from src.drift.metrics import medir_drift, _spearman_rank_correlation, _compute_ranks; assert abs(_spearman_rank_correlation([1,2,3,4],[1,2,3,4]) - 1.0) < 1e-9; print(\"metrics ok\")'"
    status: pass
    human_judgment: false
---
# Phase 01 Plan 03: Create first wave of drift service modules Summary

Extracted `GoldenSet`, `JudgeProbeRunner`, and `metrics` into isolated modules while reducing cyclomatic complexity.

## Accomplishments
- Extracted `GoldenSet` to `src/drift/golden.py` and flattened `_load()` into two helpers, preserving frozen-executable fallback and atomic save.
- Extracted `JudgeProbeRunner` to `src/drift/runner.py`, keeping its per-instance DSPy state and error-context contract intact.
- Extracted `_spearman_rank_correlation` and `medir_drift` into `src/drift/metrics.py`, promoting inner closures and extracting complex branching into flat helpers.

## Deviations from Plan
None - plan executed exactly as written.

## Self-Check: PASSED

Ready for 01-04-PLAN.md
