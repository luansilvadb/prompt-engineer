---
status: testing
phase: 01-architectural-cleanup-densification
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md]
started: 2026-07-09T21:39:14Z
updated: 2026-07-09T21:39:14Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 1
name: Backward-compatible imports via shims (old paths still resolve)
expected: |
  `from src.drift_monitor import DriftGate, GoldenSet, medir_drift, DriftReport, ProbeMeasurement`
  and `from src.mutations import registry, MutationBandit, get_mutation_prompt`
  both resolve without ImportError. drift_monitor.py and mutations.py are now thin
  re-export shims, so every existing import path keeps working (ARC-03 backward compat).
awaiting: user response

## Tests

### 1. Backward-compatible imports via shims (old paths still resolve)
expected: `from src.drift_monitor import DriftGate, GoldenSet, medir_drift, DriftReport, ProbeMeasurement` and `from src.mutations import registry, MutationBandit, get_mutation_prompt` both resolve without ImportError. drift_monitor.py and mutations.py are now thin re-export shims (ARC-03 backward compat).
result: [pending]

### 2. New package paths resolve
expected: `from src.drift.gate import DriftGate`, `from src.drift.circuit_breaker import verificar_juiz_atual, circuit_breaker`, `from src.drift.cache import load_drift_cache, save_drift_cache`, `from src.drift.golden import GoldenSet`, `from src.drift.runner import JudgeProbeRunner`, `from src.drift.metrics import medir_drift`, `from src.mutation_strategies.registry import registry`, `from src.mutation_strategies.bandit import MutationBandit`, `from src.mutation_strategies.api import get_mutation_prompt` all import cleanly (ARC-03 densified modules exist at canonical home).
result: [pending]

### 3. FastAPI app instantiates without wiring errors
expected: The FastAPI app (src/api.py / services.py) can be instantiated/imported with no ImportError, AttributeError, or circular-import error introduced by the refactor. The server wiring still binds drift + mutation components correctly (Phase Success Criteria #3).
result: [pending]

### 4. MCTS / MutationBandit runs end-to-end without LLM
expected: `MutationBandit().select()` returns a strategy string, and the MCTS/optimizer entry points (src/optimizer.py) import and are callable without requiring a live LLM call. Refactor introduced no runtime regression in the selection path (ARC-02 flattened select() preserves behavior).
result: [pending]

### 5. Dead-code cleanliness in consumer files (ARC-01)
expected: A lint/dead-code scan of the four consumer files (`src/optimizer.py`, `src/teleprompter.py`, `src/services.py`, `src/api.py`) reports no unused imports, unused local variables, or orphan functions introduced by this phase. (Pre-existing debt in out-of-scope files like experience_store.py is explicitly retained, not a failure.)
result: [pending]

### A1. src/drift/exceptions.py defining DriftMeasurementError(message, context=None)
expected: src/drift/exceptions.py defining DriftMeasurementError(message, context=None) with identical signature/behavior to drift_monitor.py L44-50
result: pass
source: automated
coverage_id: D1

### A2. src/drift/models.py with 7 drift dataclasses
expected: src/drift/models.py containing all 7 drift dataclasses with original fields/decorators/methods, including ProbeExpectation.composite_score delegation and DriftThresholds.from_config / DriftReport.to_dict
result: pass
source: automated
coverage_id: D2

### A3. StrategyRegistry + registry singleton (mutation_strategies.registry)
expected: StrategyRegistry + module-level registry singleton importable from src.mutation_strategies.registry with all public methods and atomic-persistence/resilient-fallback behavior
result: pass
source: automated
coverage_id: D1

### A4. MutationBandit with flattened select() via helpers
expected: MutationBandit with flattened select() via _pick_untried/_ucb_score helpers (no OO pattern) in src/mutation_strategies/bandit.py
result: pass
source: automated
coverage_id: D2

### A5. Thin API facade delegating to registry singleton
expected: Thin API facade get_mutation_prompt/get_strategy_description delegating to the registry singleton with identical signatures
result: pass
source: automated
coverage_id: D3

### A6. Namespace-package layout (no __init__.py; mutations.py untouched by 01-02)
expected: Namespace-package layout: no __init__.py created; src/mutations.py NOT modified by this plan (legacy path still resolves unchanged)
result: pass
source: automated
coverage_id: D4

## Summary

total: 11
passed: 6
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps

[none yet]
