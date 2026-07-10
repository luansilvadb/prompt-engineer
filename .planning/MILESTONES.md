# Milestones

## v1.0 Skill Optimizer MVP (Shipped: 2026-07-10)

**Phases completed:** 3 phases, 8 plans, 6 tasks

**Key accomplishments:**

- Foundation of the `src/drift/` namespace package — `DriftMeasurementError` and 7 drift dataclasses extracted behavior-identically from `drift_monitor.py` into `exceptions.py` + `models.py`.
- Split src/mutations.py (132-line monolith) into three single-responsibility modules under src/mutation_strategies/ (registry.py, bandit.py, api.py), with MutationBandit.select() flattened via _pick_untried/_ucb_score helpers (ARC-02, no OO pattern)
- [Rule 1 - Fix Attempt] Erro de configuração de LLM no script pontual
- Migrated teleprompter and MCTS reward function to use Mode B judge (AvaliadorModoB), incorporating strict score penalization for architectural contradictions.

---
