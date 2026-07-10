---
phase: 06-mutador-cognitivo
plan: 01
subsystem: signatures
tags: [dspy, pydantic, signatures, strategy-registry, config]
requires: []
provides:
  - RaciocinioCognitivo Pydantic model
  - MutadorCognitivoAgent DSPy Signature
  - MutadorCognitivoOutput Pydantic model
  - _validate_raciocinio post-hoc validator
  - cognitivo_prior_count and cognitivo_prior_mean_delta config keys
  - mutador_cognitivo seed in StrategyRegistry
affects: [phase 06 plan 02]
tech-stack:
  added: []
  patterns: [Pydantic field_validator with classmethod, DSPy Signature redeclared fields, standalone post-hoc validation function, hardcoded strategy seed with idempotency guard]
key-files:
  created:
    - tests/test_signatures.py
    - tests/test_config.py
    - tests/test_registry.py
  modified:
    - src/signatures.py
    - src/config.py
    - src/mutation_strategies/registry.py
    - tests/conftest.py
key-decisions:
  - "RaciocinioCognitivo uses field_validator targeting all 3 fields to enforce >= 10 char minimum"
  - "MutadorCognitivoAgent redeclares ALL fields from SelfReflectiveAgent explicitly (no class inheritance) to avoid DSPy version-dependent field inheritance behavior"
  - "MutadorCognitivoOutput validates nova_instrucao for 3 Markdown headings with .lower() normalization and soft enforcement"
  - "_validate_raciocinio is standalone post-hoc function, not wired to DSPy Signature (Risk 2 mitigation)"
  - "Seed registration is idempotent via if key not in self.strategies guard"
  - "Config keys follow MCTS_ prefix convention with int/float casts"
  - "conftest.py fixed to not replace sys.modules['src'] with mock module, allowing src.config imports"
patterns-established:
  - "DSPy Signature field declaration: redeclare all fields explicitly, do not rely on class inheritance"
  - "Post-hoc validation: standalone function that parses raw LLM string and constructs Pydantic model"
  - "Idempotent seed registration: check if key exists before calling add_strategy"
  - "Config knob: MCTS_ prefix, inline comment, explicit type cast"
requirements-completed:
  - COGN-01
coverage:
  - id: D1
    description: "RaciocinioCognitivo Pydantic model validates premissas/deducoes/conclusao are >= 10 chars"
    requirement: COGN-01
    verification:
      - kind: unit
        ref: tests/test_signatures.py#test_raciocinio_cognitivo_happy_path
        status: pass
      - kind: unit
        ref: tests/test_signatures.py#test_raciocinio_cognitivo_empty_field
        status: pass
      - kind: unit
        ref: tests/test_signatures.py#test_raciocinio_cognitivo_short_field
        status: pass
    human_judgment: false
  - id: D2
    description: "MutadorCognitivoAgent DSPy Signature exposes raciocinio_estruturado, critica, nova_instrucao outputs"
    requirement: COGN-01
    verification:
      - kind: unit
        ref: tests/test_signatures.py#test_mutador_cognitivo_agent_output_fields
        status: pass
      - kind: unit
        ref: tests/test_signatures.py#test_mutador_cognitivo_agent_input_fields
        status: pass
    human_judgment: false
  - id: D3
    description: "MutadorCognitivoOutput validates nova_instrucao contains 3 Markdown headings"
    requirement: COGN-01
    verification:
      - kind: unit
        ref: tests/test_signatures.py#test_mutador_cognitivo_output_valid
        status: pass
      - kind: unit
        ref: tests/test_signatures.py#test_mutador_cognitivo_output_missing_heading
        status: pass
    human_judgment: false
  - id: D4
    description: "_validate_raciocinio parses labeled sections and raises on missing labels"
    requirement: COGN-01
    verification:
      - kind: unit
        ref: tests/test_signatures.py#test_validate_raciocinio_valid
        status: pass
      - kind: unit
        ref: tests/test_signatures.py#test_validate_raciocinio_missing_label
        status: pass
    human_judgment: false
  - id: D5
    description: "Config keys cognitivo_prior_count and cognitivo_prior_mean_delta with env-var overrides"
    requirement: COGN-01
    verification:
      - kind: unit
        ref: tests/test_config.py#test_cognitivo_config_defaults
        status: pass
      - kind: unit
        ref: tests/test_config.py#test_cognitivo_config_override
        status: pass
    human_judgment: false
  - id: D6
    description: "StrategyRegistry seeds mutador_cognitivo key idempotently"
    requirement: COGN-01
    verification:
      - kind: unit
        ref: tests/test_registry.py#test_seed_registered
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_seed_prompt_content
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_seed_name
        status: pass
      - kind: unit
        ref: tests/test_registry.py#test_seed_idempotent
        status: pass
    human_judgment: false
duration: 22 min
completed: 2026-07-10
status: complete
---

# Phase 06 Plan 01: Foundation Layer Summary

**MutadorCognitivoAgent DSPy Signature, RaciocinioCognitivo/RaciocinioCognitivoOutput Pydantic validators, _validate_raciocinio post-hoc validator, config keys cognitivo_prior_count/cognitivo_prior_mean_delta, and mutador_cognitivo strategy seed in StrategyRegistry**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-10T06:20:00Z
- **Completed:** 2026-07-10T06:42:00Z
- **Tasks:** 2 (TDD: RED + GREEN each)
- **Files modified:** 7 (4 source, 3 test)

## Accomplishments

- Created RaciocinioCognitivo Pydantic model with 3 mandatory fields (premissas, deducoes, conclusao) each validated to be >= 10 chars
- Created MutadorCognitivoAgent DSPy Signature with 4 InputFields (redeclared from SelfReflectiveAgent) and 3 OutputFields (critica, raciocinio_estruturado, nova_instrucao)
- Created MutadorCognitivoOutput Pydantic model validating nova_instrucao contains 3 required Markdown headings (## Raciocínio, ## Regras, ## Conclusão) with .lower() normalization
- Created _validate_raciocinio standalone post-hoc validator parsing labeled sections from LLM output
- Added cognitivo_prior_count (default 4) and cognitivo_prior_mean_delta (default 0.05) config keys with MCTS_ env-var overrides
- Added _seed_hardcoded_strategies method to StrategyRegistry seeding mutador_cognitivo key idempotently
- Fixed conftest.py to not shadow the real src package with a mock module

## Task Commits

1. **Task 1 RED:** test failing tests for RaciocinioCognitivo, MutadorCognitivoAgent, etc. - `139602c`
2. **Task 1 GREEN:** feat implement RaciocinioCognitivo, MutadorCognitivoAgent, etc. - `1fbc459`
3. **Task 2 RED:** test failing tests for config keys and registry seed - `fbf1681`
4. **Task 2 GREEN:** feat implement cognitivo config keys and registry seed - `3702c30`

**Plan metadata:** `pending`

## Files Created/Modified

- `src/signatures.py` — Added RaciocinioCognitivo(BaseModel), MutadorCognitivoAgent(dspy.Signature), MutadorCognitivoOutput(BaseModel), _validate_raciocinio()
- `src/config.py` — Added cognitivo_prior_count and cognitivo_prior_mean_delta to get_mcts_config()
- `src/mutation_strategies/registry.py` — Added _seed_hardcoded_strategies() and call from __init__
- `tests/test_signatures.py` — 9 unit tests for new signatures.py types
- `tests/test_config.py` — 2 unit tests for config keys with monkeypatch
- `tests/test_registry.py` — 4 unit tests for seed registration and idempotency
- `tests/conftest.py` — Fixed mock to not replace sys.modules['src']

## Decisions Made

- SelfReflectiveAgent remains untouched (D-01 constraint verified)
- RaciocinioCognitivo uses field_validator targeting all 3 fields with @classmethod, following GeracaoSkill pattern
- MutadorCognitivoAgent redeclares all fields explicitly (no class inheritance) per DSPy field inheritance caveat
- _validate_raciocinio is standalone function, not wired to DSPy Signature (Risk 2 mitigation)
- Config keys follow MCTS_ prefix convention with inline Portuguese comments
- Seed registration is idempotent: checks if key exists before calling add_strategy

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing test failures: test_heuristic_evaluator.py::test_layer_2_penalty and test_optimizer.py::test_optimizer_layer2_penalty_multiplier (both pre-existing, not caused by this plan)
- conftest.py had a bug where it replaced sys.modules['src'] with a mock ModuleType, breaking imports for modules not already cached (e.g. src.config). Fixed by only mocking src.ausculta_modo_b instead of the entire src package.

## Next Phase Readiness

Ready for Plan 06-02 (Optimizer integration: prior boosting, strategy routing, integration tests).
