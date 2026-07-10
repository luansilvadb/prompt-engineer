---
phase: 05
slug: avaliador-de-profundidade-heur-stica
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none — see Wave 0 |
| **Quick run command** | `pytest -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -x`
- **After every plan wave:** Run `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | COGN-03 | — | N/A | unit | `pytest tests/test_heuristic_evaluator.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | COGN-03 | — | N/A | integration | `pytest tests/test_optimizer.py -k "test_heuristic_injection" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_heuristic_evaluator.py` — stubs for COGN-03
- [ ] `tests/test_optimizer.py` — stubs for COGN-03 MCTS integration
- [ ] `tests/conftest.py` — shared fixtures for "hollow verbosity" vs "dense reasoning" datasets
- [ ] MCTS mocking infrastructure for LLM/Embeddings

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| System Performance | COGN-03 | API cost/time reduction is emergent | Run full MCTS loop on sample prompt and verify API calls count compared to baseline |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
