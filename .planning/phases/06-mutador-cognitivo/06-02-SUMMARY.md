# Plan 06-02 Summary: Prior Boosting, Agent Cognitivo Instantiation & Routing

## Goal
Bind the `MutadorCognitivoAgent` signature into `Optimizer` as a live DSPy module, give it an unconditional prior boost in `load_priors`, and route `_expand_node` to call `agent_cognitivo` when `mutation_bandit` selects the `'mutador_cognitivo'` strategy.

## Commits
| SHA | Message |
|-----|---------|
| `064c17b` | test: failing tests for bandit and optimizer |
| `4c3d431` | feat: implement agent_cognitivo instantiation and cognitivo prior boosting in `Optimizer.__init__` |
| `cf3e717` | test: add failing integration tests for cognitivo routing and regression test |
| `2eeef71` | feat: add strategy-based routing in `_expand_node` with cognitivo branch and soft validation |

## Files Changed
- `src/optimizer.py` — 3 changesets:
  1. Updated imports (`MutadorCognitivoAgent`, `MutadorCognitivoOutput`, `_validate_raciocinio`)
  2. Added `self.agent_cognitivo = dspy.ChainOfThought(MutadorCognitivoAgent)` in `__init__`
  3. Added unconditional prior boost via `load_priors`
  4. Added strategy-based routing in `_expand_node`: `if strategy == 'mutador_cognitivo'` branch with soft validation
- `tests/test_optimizer_integration.py` — new file with 4 integration tests
- `tests/test_optimizer.py` — added `test_optimizer_cognitivo_regression`

## Test Results
- **32 pass**, 2 pre-existing failures (unchanged — `test_layer_2_penalty`, `test_optimizer_layer2_penalty_multiplier`)
- All 5 new tests pass (4 integration + 1 regression)
- Pre-existing conftest fix verified: no `sys.modules['src']` shadowing, no `autospec=True`

## Key Decisions (D-01 to D-04 from CONTEXT)
- D-01: SelfReflectiveAgent unchanged ✓
- D-02: Cognitivo as separate agent ✓ (routed by strategy name)
- D-03: Soft validation wrappers ✓ (try/except with `on_error`)
- D-04: Task 2 routing tested ✓ (4 integration tests for `_expand_node`)

## Delta from Plan
- Integration test `test_cognitivo_integration_child_strategy` was simplified to check `_run_mcts_iteration` return tuple rather than asserting child is not None, since the method returns `(should_break, is_error, reward)`.

## Artifacts
- `.planning/phases/06-mutador-cognitivo/06-02-PLAN.md` — reference plan document
- `.planning/phases/06-mutador-cognitivo/06-CONTEXT.md` — phase-level decisions
