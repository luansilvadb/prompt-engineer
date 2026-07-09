---
phase: 01-architectural-cleanup-densification
plan: 02
subsystem: api
tags: [python, refactoring, mcts, ucb1-bandit, namespace-package, arc-02, arc-03]

# Dependency graph
requires:
  - phase: (none — greenfield extraction from existing src/mutations.py)
    provides: n/a
provides:
  - "src/mutation_strategies/ namespace package (registry.py, bandit.py, api.py) — single-responsibility split of the mutations monolith"
  - "StrategyRegistry + module-level `registry` singleton importable from src.mutation_strategies.registry"
  - "MutationBandit with flattened select() (ARC-02 helpers _pick_untried/_ucb_score)"
  - "Thin API facade get_mutation_prompt/get_strategy_description delegating to the registry singleton"
affects:
  - "01-05 (mutations.py shim): re-export these symbols from the legacy path"
  - "src/optimizer.py (consumes registry, MutationBandit, get_mutation_prompt, get_strategy_description)"
  - "test_discoverer.py (consumes registry)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Namespace package (zero __init__.py) — matches src/routers/ convention"
    - "Atomic file persistence via temp file + os.replace (Shared Pattern #3)"
    - "Cyclomatic-complexity reduction via small private helper METHODS, NOT OO Strategy/Policy (CONTEXT D-02)"

key-files:
  created:
    - src/mutation_strategies/registry.py
    - src/mutation_strategies/bandit.py
    - src/mutation_strategies/api.py
  modified: []

key-decisions:
  - "Package named mutation_strategies (NOT mutations) — a directory cannot share a name with the existing src/mutations.py module file (Python ImportError); deviation noted in plan objective"
  - "save() upgraded to atomic temp+os.replace idiom (required by plan AC + PATTERNS Shared Pattern #3 + threat T-01-02); resilient swallow-and-continue fallback preserved unchanged"
  - "_pick_untried preserves random.choice among untried arms (CONTEXT D-02 'apenas redução de complexidade de leitura' forbids behavior change); the plan's 'first key' prose was treated as loose description since acceptance criteria only require the helper to exist"

patterns-established:
  - "Extract-then-shim: behavior-preserving relocation into a namespace package, with the legacy module kept intact for a later re-export-shim plan (01-05)"
  - "Flatten select()-style dispatch by promoting inline closures to named private methods"

requirements-completed: [ARC-02, ARC-03]

# Coverage metadata (#1602)
coverage:
  - id: D1
    description: "StrategyRegistry + module-level `registry` singleton importable from src.mutation_strategies.registry with all public methods and atomic-persistence/resilient-fallback behavior"
    requirement: ARC-03
    verification:
      - kind: other
        ref: 'command: python -c "from src.mutation_strategies.registry import StrategyRegistry, registry; assert isinstance(registry, StrategyRegistry); print(''registry ok'')"  (exited 0, printed "registry ok")'
        status: pass
    human_judgment: false
  - id: D2
    description: "MutationBandit with flattened select() via _pick_untried/_ucb_score helpers (no OO pattern) in src/mutation_strategies/bandit.py"
    requirement: ARC-02
    verification:
      - kind: other
        ref: 'command: python -c "from src.mutation_strategies.bandit import MutationBandit; b=MutationBandit(); s=b.select(); assert isinstance(s,str); print(''select returned'', repr(s))"  (exited 0, returned a strategy string)'
        status: pass
    human_judgment: false
  - id: D3
    description: "Thin API facade get_mutation_prompt/get_strategy_description delegating to the registry singleton with identical signatures"
    requirement: ARC-03
    verification:
      - kind: other
        ref: 'command: python -c "from src.mutation_strategies.api import get_mutation_prompt, get_strategy_description; print(''ok'')"  (exited 0)'
        status: pass
    human_judgment: false
  - id: D4
    description: "Namespace-package layout: no __init__.py created; src/mutations.py NOT modified by this plan (legacy path still resolves unchanged)"
    requirement: ARC-03
    verification:
      - kind: other
        ref: 'filesystem: Test-Path src/mutation_strategies/__init__.py = false; git log src/mutations.py last touch = d7c6d34 (pre-existing); python -c "from src.mutations import registry, MutationBandit, ..." exited 0 ("legacy ok")'
        status: pass
    human_judgment: false

# Metrics
duration: 3 min
completed: 2026-07-09
status: complete
---

# Phase 01 Plan 02: Mutation Strategies Split Summary

**Split src/mutations.py (132-line monolith) into three single-responsibility modules under src/mutation_strategies/ (registry.py, bandit.py, api.py), with MutationBandit.select() flattened via _pick_untried/_ucb_score helpers (ARC-02, no OO pattern)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-09T19:01:27Z
- **Completed:** 2026-07-09T19:04:55Z
- **Tasks:** 2
- **Files modified:** 3 (all new)

## Accomplishments
- Extracted `StrategyRegistry` + module-level `registry` singleton into `src/mutation_strategies/registry.py`, preserving every method (`__init__`, `_store_path`, `_load`, `save`, `add_strategy`, `get_prompt`, `get_name`, `get_all_keys`), the `STRATEGIES_DIR` constant, the `__DISCOVER__` special-casing, and the resilient load-failure fallback
- Extracted `MutationBandit` into `src/mutation_strategies/bandit.py` and reduced `select()` cyclomatic complexity via two private helper methods (`_pick_untried`, `_ucb_score`) — `select()` now reads as a flat sequence (ensure keys → try untried → else UCB1 max). No ABC/Strategy/Policy hierarchy introduced (CONTEXT D-02)
- Added thin API facade `src/mutation_strategies/api.py` (`get_mutation_prompt`, `get_strategy_description`) delegating to the registry singleton with identical signatures
- Verified the legacy `src/mutations.py` still imports unchanged (back-compat preserved until plan 01-05 converts it to a re-export shim)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract StrategyRegistry + singleton into src/mutation_strategies/registry.py** — `49baf02` (feat)
2. **Task 2: Extract MutationBandit (ARC-02 helpers) and API facade** — `a397633` (feat)

_Plan metadata commit follows below._

## Files Created/Modified
- `src/mutation_strategies/registry.py` — StrategyRegistry class + module-level `registry` singleton + STRATEGIES_DIR constant; atomic save() (temp + os.replace), resilient load fallback
- `src/mutation_strategies/bandit.py` — MutationBandit class with flattened select() (_pick_untried, _ucb_score helpers); imports `registry` from registry.py
- `src/mutation_strategies/api.py` — thin facade: get_mutation_prompt / get_strategy_description delegate to registry singleton

## Decisions Made
- **Package name `mutation_strategies` (not `mutations`):** A directory cannot share a name with the existing `src/mutations.py` module file in Python — the file shadows the directory and `from src.mutations.registry import ...` raises ImportError (verified in plan objective). The new package is `src/mutation_strategies/`; the legacy `src/mutations.py` is preserved verbatim for now and becomes a re-export shim in plan 01-05.
- **`save()` upgraded to atomic temp+`os.replace`:** The plan's `<action>`, acceptance criteria (`os.replace(`), PATTERNS Shared Pattern #3, and threat-model T-01-02 all require the atomic-write idiom. The original `save()` wrote directly; the upgrade is a strictly-safer write path (identical file content), and the resilient swallow-and-continue `except Exception: pass` fallback is preserved unchanged (CONTEXT: no behavioral contract change).
- **`_pick_untried` preserves `random.choice`:** The plan prose says "returns the first strategy key with zero pulls", but CONTEXT D-02 restricts scope to *"apenas na redução da complexidade de leitura"* (ONLY reading-complexity reduction), and the plan's `<artifacts_this_plan_produces>` states *"Behavior is externally unchanged (same I/O)"*. The original used `random.choice(untried)`; switching to deterministic "first" would change the observable exploration distribution (relevant for the Tabula Rasa discovery system). PATTERNS L404 maps the helper to lines 110-112 which include `random.choice`. The Task-2 acceptance criteria only require the helper to *exist* — so behavior preservation governs, and `random.choice` is kept inside the helper. `select()` I/O is byte-for-byte identical to the original given the same RNG state.

## Deviations from Plan

None requiring a rule-triggered auto-fix. Two clarifying interpretation decisions (documented above in "Decisions Made") where the plan's prose was looser than its hard invariants (acceptance criteria + CONTEXT D-02 + threat model), both resolved in favor of the hard invariants:

1. **`save()` atomicity** — the literal source did not contain `os.replace`, but the plan `<action>`, acceptance criteria, and threat model all mandate it; implemented as required.
2. **`_pick_untried` selection policy** — plan prose said "first", but CONTEXT D-02 + plan artifacts invariant mandate unchanged behavior; preserved `random.choice`.

Neither changes the externally observable contract. No code failed to compile or import; all acceptance criteria and the plan-level `<verification>` block passed on the first attempt.

**Total deviations:** 0 auto-fixed (2 clarifying interpretation decisions, behavior-preserving)
**Impact on plan:** None — plan executed exactly as intended. All 9 source/acceptance assertions, the 6 plan-level verification commands, and the full import smoke test passed.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The `src/mutation_strategies/` namespace package is complete and importable; ready for plan 01-05 to convert `src/mutations.py` into a re-export shim that imports from these three modules (the shim will preserve all existing `from src.mutations import ...` consumers in `optimizer.py` and `test_discoverer.py`).
- No blockers. The legacy path `src.mutations.*` continues to resolve unchanged in the meantime.

---
*Phase: 01-architectural-cleanup-densification*
*Completed: 2026-07-09*

## Self-Check: PASSED

Files verified to exist on disk:
- FOUND: `src/mutation_strategies/registry.py`
- FOUND: `src/mutation_strategies/bandit.py`
- FOUND: `src/mutation_strategies/api.py`
- PASS: `src/mutation_strategies/__init__.py` does NOT exist (namespace package)

Commits verified in git log:
- FOUND: `49baf02` (feat(01-02): extract StrategyRegistry)
- FOUND: `a397633` (feat(01-02): extract MutationBandit + API facade)

Invariants verified:
- PASS: `src/mutations.py` last touched by `d7c6d34` (pre-existing) — NOT modified by this plan
- PASS: legacy `from src.mutations import registry, MutationBandit, ...` still resolves ("legacy ok")
- PASS: full smoke `from src.mutation_strategies.{registry,bandit,api} import ...` resolves; `type(registry).__name__ == 'StrategyRegistry'`
- PASS: `MutationBandit().select()` returns a strategy string
- PASS: no relative imports in any of the three files
