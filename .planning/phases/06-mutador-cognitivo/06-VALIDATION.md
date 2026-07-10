---
phase: 06
slug: mutador-cognitivo
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `tests/conftest.py` |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | COGN-01 | — | N/A | unit | `pytest tests/test_signatures.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | COGN-01 | — | N/A | unit | `pytest tests/test_signatures.py::test_raciocinio_cognitivo -x -q` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | COGN-01 | — | N/A | unit | `pytest tests/test_registry.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 2 | COGN-01 | — | N/A | unit | `pytest tests/test_bandit.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 2 | COGN-01 | — | N/A | unit | `pytest tests/test_optimizer.py -x -q` | ✅ | ⬜ pending |
| 06-01-06 | 01 | 2 | COGN-01 | — | N/A | unit | `pytest tests/test_config.py -x -q` | ❌ W0 | ⬜ pending |
| 06-01-07 | 01 | 3 | COGN-01 | — | N/A | integration | `pytest tests/test_optimizer_integration.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_signatures.py` — stubs for `MutadorCognitivoAgent` field inspection and `RaciocinioCognitivo` Pydantic validator tests
- [ ] `tests/test_registry.py` — stubs for seed registration and idempotency tests (or extend existing registry tests)
- [ ] `tests/test_bandit.py` — stubs for prior boosting and UCB1 selection tests (or extend existing bandit tests)
- [ ] `tests/test_config.py` — stubs for new `cognitivo_prior_count` / `cognitivo_prior_mean_delta` config keys
- [ ] `tests/test_optimizer_integration.py` — stubs for integration smoke test (no LLM)

*Existing `tests/conftest.py` shared fixtures available. `tests/test_optimizer.py` already exists — routing intercept regression tests extend it.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `nova_instrucao` from MutadorCognitivoAgent visually contains `## Raciocínio`, `## Regras`, `## Conclusão` in a real LLM run | COGN-01 | Requires live LLM call | Run `python -m src.optimizer` with a test skill and log `nova_instrucao` from a `mutador_cognitivo` expansion |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
