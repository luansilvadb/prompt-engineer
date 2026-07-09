---
phase: 01-architectural-cleanup-densification
plan: 01
subsystem: infra
tags: [python, dataclasses, namespace-package, refactor, drift-monitor, pure-extraction]

# Dependency graph
requires:
  - phase: none
    provides: greenfield extraction (no prior phase needed)
provides:
  - "src/drift/ namespace package foundation (exceptions.py + models.py)"
  - "DriftMeasurementError(message, context=None) domain exception"
  - "Drift dataclasses (ProbeExpectation, GoldenProbe, DimensionError, DriftReport, GateDecision, DriftThresholds, ProbeMeasurement) in canonical home"
  - "ProbeExpectation.composite_score delegation to src.signatures.calcular_composite"
affects: [01-02, 01-05, drift-monitor-shim, golden, runner, metrics, gate, circuit_breaker, cache]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Python 3 implicit namespace package (src/drift/ — no __init__.py, mirrors src/routers/)"
    - "Dataclass immutability convention: @dataclass(frozen=True) for value objects; plain @dataclass + field(default_factory=list) for aggregators"
    - "Single-responsibility module: one exception class per exceptions.py"
    - "Absolute src-rooted imports (from src.X import Y); no relative imports"

key-files:
  created:
    - src/drift/exceptions.py
    - src/drift/models.py
  modified: []

key-decisions:
  - "Pure relocation, not rewrite — byte-for-behavior-identical extraction from drift_monitor.py"
  - "ProbeMeasurement included in models.py even though it sits at drift_monitor.py L255-307 (plan listed it in must_haves + acceptance criteria even while the action text referenced only L57-148)"
  - "Added statistics + time + Avaliacao imports to models.py beyond the plan's enumerated list (required to preserve identical behavior of ProbeMeasurement methods and DriftReport.to_dict)"

patterns-established:
  - "src/drift/ namespace package layout (no __init__.py) — template for golden/runner/metrics/gate/circuit_breaker/cache plans"
  - "Extraction commit message convention: feat(01-01): extract <X> into src/drift/<Y>.py"

requirements-completed: [ARC-03]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "src/drift/exceptions.py defining DriftMeasurementError(message, context=None) with identical signature/behavior to drift_monitor.py L44-50"
    requirement: ARC-03
    verification:
      - kind: other
        ref: 'python -c "from src.drift.exceptions import DriftMeasurementError; e=DriftMeasurementError(''m'', context={''k'':1}); assert e.message==''m'' and e.context=={''k'':1}; e2=DriftMeasurementError(''x''); assert e2.context=={}; print(''exceptions ok'')"'
        status: pass
    human_judgment: false
  - id: D2
    description: "src/drift/models.py containing all 7 drift dataclasses (ProbeExpectation, GoldenProbe, DimensionError, DriftReport, GateDecision, DriftThresholds, ProbeMeasurement) with original fields/decorators/methods, including ProbeExpectation.composite_score delegation and DriftThresholds.from_config / DriftReport.to_dict"
    requirement: ARC-03
    verification:
      - kind: other
        ref: 'python -c "from src.drift.models import ProbeExpectation, GoldenProbe, DimensionError, DriftReport, GateDecision, DriftThresholds, ProbeMeasurement; t=DriftThresholds.from_config({''spearman_floor'':0.8}); print(type(t).__name__, ''models ok'')"'
        status: pass
    human_judgment: false

# Metrics
duration: 2 min
completed: 2026-07-09
status: complete
---

# Phase 1 Plan 1: Drift Namespace Foundation Summary

**Foundation of the `src/drift/` namespace package — `DriftMeasurementError` and 7 drift dataclasses extracted behavior-identically from `drift_monitor.py` into `exceptions.py` + `models.py`.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-07-09T18:55:04Z
- **Completed:** 2026-07-09T18:57:30Z
- **Tasks:** 2
- **Files modified:** 2 (both new files)

## Accomplishments
- `src/drift/exceptions.py` — single-class module holding `DriftMeasurementError(message, context=None)`; signature, docstring, and `context or {}` default preserved verbatim from `drift_monitor.py` L44-50.
- `src/drift/models.py` — all 7 drift dataclasses relocated with original fields, defaults, immutability decorators, and classmethods intact. `ProbeExpectation.composite_score` still delegates to `src.signatures.calcular_composite`; `DriftThresholds.from_config` and `DriftReport.to_dict` travel with their owning classes.
- Namespace-package invariant honored: **zero `__init__.py`** created anywhere (matches `src/routers/` convention and the repo-wide invariant).
- Cross-module link preserved: `from src.signatures import calcular_composite` (and `Avaliacao`) imported via absolute src-rooted path.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract DriftMeasurementError into src/drift/exceptions.py** — `3df55ed` (feat)
2. **Task 2: Extract all drift dataclasses into src/drift/models.py** — `85ef681` (feat)

## Files Created/Modified
- `src/drift/exceptions.py` — domain exception `DriftMeasurementError(message, context=None)`; the single error vocabulary every drift service module will raise.
- `src/drift/models.py` — domain data layer: 5 frozen value objects (`ProbeExpectation`, `GoldenProbe`, `DimensionError`, `GateDecision`, `DriftThresholds`) + 2 mutable aggregators (`DriftReport`, `ProbeMeasurement`).

## Decisions Made
- **Pure relocation, not rewrite.** Every field name, type, default, decorator, and method body is byte-identical to the source. No behavior change — by design (this plan is the dependency-free leaf of the densification).
- **`ProbeMeasurement` included in models.py.** The plan's Task 2 `<action>` text said "L57-148", but the `must_haves`, `acceptance_criteria`, and `artifacts_this_plan_produces` all list `ProbeMeasurement` as a required deliverable (it actually lives at `drift_monitor.py` L255-307). Honored the explicit success criteria.
- **Added `statistics` + `time` + `Avaliacao` imports.** The plan's Task 2 "Imports" bullet enumerated only `from typing import Optional, List`, `from dataclasses import dataclass, field`, and `from src.signatures import calcular_composite`. But `ProbeMeasurement` (which the same task requires) uses `statistics.mean` / `statistics.pstdev` and a `List[Avaliacao]` field type, and `DriftReport.to_dict` calls `time.time()`. Without these imports the file would not load and acceptance criterion "import resolves" would fail. Added them to keep the extraction behavior-identical (Rule 2).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added under-enumerated imports to models.py**
- **Found during:** Task 2 (Extract drift dataclasses)
- **Issue:** Plan's Task 2 "Imports" list named only `calcular_composite` (cross-module) + `typing` + `dataclasses`. But the same task requires relocating `ProbeMeasurement` (uses `statistics.mean`, `statistics.pstdev`, `List[Avaliacao]`) and `DriftReport.to_dict` (uses `time.time()`). Without `import statistics`, `import time`, and `from src.signatures import Avaliacao`, the file fails to import and every acceptance criterion in Task 2 fails.
- **Fix:** Added `import statistics`, `import time`, and extended the signatures import to `from src.signatures import Avaliacao, calcular_composite`.
- **Files modified:** `src/drift/models.py`
- **Verification:** `python -c "from src.drift.models import ..."` exits 0 and prints "DriftThresholds models ok".
- **Committed in:** `85ef681` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Zero scope creep — the added imports are strictly necessary to satisfy the plan's own acceptance criteria (behavior-identical extraction + import resolves). No behavior change introduced.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required. Pure in-process Python relocation.

## Next Phase Readiness
- ✅ `src/drift/` namespace package exists with the two dependency-free leaf modules. Ready for the next plans in this phase:
  - **01-02** (`src/mutation_strategies/` foundation) — independent sibling, can proceed in parallel.
  - **01-03 / 01-04** (golden / runner / metrics / gate / circuit_breaker / cache extraction) — will `from src.drift.models import ...` and `from src.drift.exceptions import DriftMeasurementError`.
  - **01-05** — turns `src/drift_monitor.py` into a re-export shim so existing `from src.drift_monitor import X` paths keep working (old copies of these classes remain there until then — intentional temporary duplication).
- No blockers.

## Self-Check: PASSED

- ✅ `[ -f src/drift/exceptions.py ]` → FOUND
- ✅ `[ -f src/drift/models.py ]` → FOUND
- ✅ `[ ! -f src/drift/__init__.py ]` → confirmed (no __init__.py)
- ✅ `git log --oneline --all | grep 3df55ed` → FOUND (Task 1)
- ✅ `git log --oneline --all | grep 85ef681` → FOUND (Task 2)
- ✅ Plan-level verification command passes: `from src.drift.exceptions import DriftMeasurementError; from src.drift.models import ProbeExpectation, GoldenProbe, DimensionError, DriftReport, GateDecision, DriftThresholds, ProbeMeasurement` → "plan verification ok"

---
*Phase: 01-architectural-cleanup-densification*
*Completed: 2026-07-09*
