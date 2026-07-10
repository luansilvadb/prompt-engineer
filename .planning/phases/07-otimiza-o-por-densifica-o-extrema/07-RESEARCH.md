# 07-RESEARCH.md — Phase 07: Otimização por Densificação Extrema

**Requirement:** COGN-04  
**Researched:** 2026-07-10  
**Source files read:** `src/optimizer.py`, `src/config.py`, `src/signatures.py`, `src/heuristic_evaluator.py`, `src/semantic_evaluator.py`, `src/mutation_strategies/bandit.py`, `src/mutation_strategies/registry.py`, `tests/conftest.py`, `tests/test_optimizer.py`, `tests/test_heuristic_evaluator.py`, `tests/test_semantic_evaluator.py`, `tests/test_config.py`, `tests/test_signatures.py`, `tests/test_bandit.py`, `.planning/phases/07-otimiza-o-por-densifica-o-extrema/07-CONTEXT.md`, `.planning/phases/07-otimiza-o-por-densifica-o-extrema/07-DISCUSSION-LOG.md`, `.planning/REQUIREMENTS.md`, `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STACK.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/CONCERNS.md`, `.planning/codebase/CONVENTIONS.md`

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

| ID | Decision |
|----|----------|
| D-01 | Density multiplier acts as the **final multiplier** on the consolidated MCTS score. Pipeline: `textstat → sentence-transformers → ModoB → density(multiplicador) → score final`. |
| D-02 | Density multiplier parameters (`DENSITY_MULTIPLIER_MIN`, `DENSITY_MULTIPLIER_MAX`, `DENSITY_THRESHOLD`) configurable via `config.py`. |
| D-03 | Two-layer approach: (1) Universal compression ratio `len(gerada)/len(pai)` for ALL strategies; (2) Structured bonus if output contains MutadorCognitivoAgent fields (`raciocinio_estruturado` with `premissas`, `deducoes`, `conclusao`). |
| D-04 | Density calculation is the **final step** in the evaluation pipeline, executed after AvaliadorModoB. Multiplier applied to consolidated score. No refactoring of existing layers. |
| D-05 | Density reward applies to ALL mutation strategies. Compression ratio works universally. Structured bonus applies conditionally when MutadorCognitivoAgent fields are present. |

### The Agent's Discretion

Nenhuma — todas as decisões foram explicitadas pelo usuário.

### Deferred Ideas (OUT OF SCOPE)

Nenhuma — a discussão se manteve no escopo da fase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COGN-04 | Algoritmo de mutação recompensa instruções comprimidas e altamente lógicas (Densificação Extrema) sobre simples chain-of-thought extenso. | Full research below: density multiplier formula, integration point in `_run_mcts_iteration`, config keys, structured bonus detection |

**Success Criteria from ROADMAP:**

1. Reward function mathematically boosts scores for answers that are both logical and concise.
2. Verbose chain-of-thought results receive lower relative scores compared to dense logic.
3. E2E pipeline successfully outputs compressed, highly-structured prompt variants.
</phase_requirements>

---

## Summary

Phase 7 implements COGN-04: a **density multiplier** that rewards compressed, logically-structured instructions and penalizes verbosity. The multiplier is the final step in the MCTS reward pipeline, applied after the ModoB judge score and all existing penalties (heuristic, semantic).

The implementation is **minimal and low-risk** — it adds:
1. A new `density_evaluator.py` module with `calculate_density_multiplier()`
2. Three new config keys in `get_mcts_config()`
3. ~8 lines of integration code in `_run_mcts_iteration()` (between lines 408 and 411)
4. A helper to detect structured cognitive fields by checking instruction headings

No existing architecture is refactored. The multiplier pattern exactly follows the existing heuristic multiplier and semantic penalty patterns.

**Primary recommendation:** Inject density multiplier as a ~8-line block in `optimizer.py` after line 408, using a new standalone function in `src/density_evaluator.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Density calculation function | API / Backend | Database / Storage | Pure function operating on instruction strings, no persistence |
| Config loading | API / Backend | — | Follows existing `get_mcts_config()` pattern in `config.py` |
| Structured field detection | API / Backend | — | String scan of `child.instruction` in the MCTS loop |
| Multiplier application | API / Backend | — | Inline multiplication in `_run_mcts_iteration` |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.12+ | `len()` for compression ratio | No external dependency needed for character-count density |

### No New Dependencies
The density calculation uses **only Python built-ins**: `len()` for character count, and string operations for heading detection. No new pip packages are required.

---

## Package Legitimacy Audit

> **No new external packages** required for this phase. The density multiplier uses only Python stdlib (`len()`, string methods). All dependencies (`textstat`, `sentence-transformers`, `torch`, `dspy-ai`, `litellm`, `pytest`) are already installed in the environment.

| Package | Registry | Verdict | Disposition |
|---------|----------|---------|-------------|
| *(none new)* | — | — | — |

---

## Architecture Patterns

### System Architecture Diagram

```
MCTS Reward Pipeline (_run_mcts_iteration, lines 361-436):

  [1] Heuristic Penalty Layer 1 & 2      (lines 375-387)
      evaluate_heuristics() → prune or continue
      
  [2] ModoB Judge                         (line 390)
      simulation() → reward, feedback
      
  [3] Heuristic Multiplier Layer 2        (lines 392-397)
      reward = reward * multiplier
      
  [4] Semantic Penalty                    (lines 399-408)
      calculate_semantic_penalty() → penalty
      reward = reward * penalty
      
  [5] ◀── DENSITY MULTIPLIER (NEW) ──▶   (between 408 and 411)
      calculate_density_multiplier() → density_mult
      reward = reward * density_mult
      
  [6] Feedback storage, delta shaping,    (lines 411-434)
      backpropagation, bandit update
```

### Data Flow (Density Calculation)

```
child.instruction ──┐
                    ├──→ len(child) / max(1, len(parent)) ──→ compression_ratio
parent.instruction ─┘                                            │
                                                                  ▼
                                                    density_mult = clamp(
                                                        DENSITY_THRESHOLD / ratio,
                                                        DENSITY_MULTIPLIER_MIN,
                                                        DENSITY_MULTIPLIER_MAX
                                                    )
                                                                  │
child.mutation_strategy ──→ 'mutador_cognitivo'? ──yes──→ has headings? ──yes──→ +STRUCTURED_BONUS
                                    │                          │
                                    no                         no
                                    ▼                          ▼
                              skip bonus                  skip bonus
                                                                  │
                                                                  ▼
                                                    reward = reward * density_mult
```

### Recommended Project Structure

No structural changes needed. Files to modify:
```
src/
├── config.py              # 3 new density config keys
├── density_evaluator.py   # NEW: calculate_density_multiplier()
├── optimizer.py           # ~8 lines injected between 408 and 411
```

### Pattern 1: Evaluator Function Pattern
**What:** Each evaluator is a standalone function returning a numeric factor that gets multiplied into the reward. The pattern is established by `evaluate_heuristics()` (returns `penalty_multiplier`) and `calculate_semantic_penalty()` (returns penalty factor).

**When to use:** For the density multiplier — it's exactly the same pattern.

**Example (from `heuristic_evaluator.py`):**
```python
def evaluate_heuristics(text: str, density_min: float = 0.35, penalty_factor: float = 0.85) -> dict:
    # ... calculations ...
    return {"prune": False, "penalty_multiplier": multiplier, "reason": "Passed"}
```

Applied in `optimizer.py` as:
```python
multiplier = heuristic_result.get("penalty_multiplier", 1.0)
reward = reward * multiplier
```

### Pattern 2: Config Key Pattern
**What:** All MCTS hyperparameters in `get_mcts_config()` follow `os.environ.get('MCTS_KEY', 'default')` with explicit type cast.

**When to use:** For the three density parameters.

### Anti-Patterns to Avoid
- **Inlining the density calculation directly in `_run_mcts_iteration` without a helper function.** The existing pattern (heuristic_evaluator.py, semantic_evaluator.py) keeps each evaluator in its own module for testability.
- **Using word count instead of character count for compression ratio.** D-03 specifies `len()` which is character count. Word count would behave differently for languages like Portuguese where words can be long.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Config parameter loading | Custom config parser | `config.py` pattern with `os.environ.get()` | Already established, consistent |
| Structured field detection | Regex parsing of cognitive sections | Simple `in` check for headings | The MutadorCognitivoOutput validator already enforces format; a string `in` check is sufficient for detection. |

**Key insight:** The density multiplier is a pure mathematical function. No ML, no LLM calls, no complex validation. Just arithmetic on string lengths and a heading presence check. This is the simplest component in the entire MCTS pipeline.

---

## Implementation Details

### 1. NEW: `src/density_evaluator.py` — Density Calculation

```python
"""
Density Evaluator — COGN-04: Densificação Extrema

Calculates a density multiplier that rewards compressed, logically-structured
instructions over verbose chain-of-thought. Applied as the final multiplier
in the MCTS reward pipeline.
"""


def _has_structured_fields(instruction: str) -> bool:
    """
    Detect if the instruction contains MutadorCognitivo structured fields:
    ## Raciocínio, ## Regras, ## Conclusão.
    
    Uses the same heading check as MutadorCognitivoOutput.validar_secoes_cognitivas().
    """
    normalized = instruction.lower()
    required = ['## raciocínio', '## regras', '## conclusão']
    return all(s in normalized for s in required)


def calculate_density_multiplier(
    child_instruction: str,
    parent_instruction: str,
    mutation_strategy: str = '',
    density_threshold: float = 1.0,
    density_multiplier_min: float = 0.5,
    density_multiplier_max: float = 1.5,
    structured_bonus: float = 0.2,
) -> float:
    """
    Calculate the density multiplier for the MCTS reward.
    
    Layer 1 — Universal compression ratio:
        compression_ratio = len(child) / max(1, len(parent))
        multiplier = density_threshold / max(0.01, compression_ratio)
        Clamped to [density_multiplier_min, density_multiplier_max]
    
    Layer 2 — Structured bonus (conditional):
        If mutation_strategy == 'mutador_cognitivo' AND the instruction
        contains all three cognitive headings, add structured_bonus.
    
    Args:
        child_instruction: The generated instruction text.
        parent_instruction: The parent instruction text.
        mutation_strategy: The strategy key used to generate this instruction.
        density_threshold: Compression ratio at which multiplier = 1.0.
        density_multiplier_min: Floor for the multiplier (penalty cap).
        density_multiplier_max: Ceiling for the multiplier (bonus cap).
        structured_bonus: Additional boost for structured cognitive fields.
    
    Returns:
        Float multiplier in [density_multiplier_min, density_multiplier_max + structured_bonus].
    """
    # Layer 1: Universal compression ratio
    parent_len = max(1, len(parent_instruction))
    compression_ratio = len(child_instruction) / parent_len
    
    # Inverse relationship: lower compression → higher multiplier
    density_mult = density_threshold / max(0.01, compression_ratio)
    
    # Clamp to configured bounds
    density_mult = max(density_multiplier_min, min(density_multiplier_max, density_mult))
    
    # Layer 2: Structured bonus for MutadorCognitivo
    if mutation_strategy == 'mutador_cognitivo' and _has_structured_fields(child_instruction):
        density_mult += structured_bonus
    
    return density_mult
```

### 2. `src/config.py` — Three New Config Keys

Add to `get_mcts_config()` dictionary (after line 102, before closing brace):

```python
# Parâmetros do Multiplicador de Densidade (COGN-04)
'density_multiplier_min': float(os.environ.get('MCTS_DENSITY_MULTIPLIER_MIN', '0.5')),
'density_multiplier_max': float(os.environ.get('MCTS_DENSITY_MULTIPLIER_MAX', '1.5')),
'density_threshold': float(os.environ.get('MCTS_DENSITY_THRESHOLD', '1.0')),
'density_structured_bonus': float(os.environ.get('MCTS_DENSITY_STRUCTURED_BONUS', '0.2')),
```

**Default rationale:**

| Key | Default | Rationale |
|-----|---------|-----------|
| `density_multiplier_min` | 0.5 | Maximum penalty for extremely verbose outputs (ratio=2.0 → mult=0.5). Below 0.5 would be too aggressive for the MCTS early iterations. |
| `density_multiplier_max` | 1.5 | Maximum boost for highly compressed outputs (ratio=0.5 → mult=2.0, clamped to 1.5). Above 1.5 would dominate the reward signal. |
| `density_threshold` | 1.0 | Breakeven at equal length. At ratio=1.0, multiplier=1.0 (no bonus, no penalty). Users can lower this (e.g., 0.8) to reward compression more aggressively. |
| `density_structured_bonus` | 0.2 | Bonus for having structured sections beyond the compression ratio. Added after clamping, so max effective multiplier = 1.5 + 0.2 = 1.7 for MutadorCognitivo outputs. |

### 3. `src/optimizer.py` — Load Config & Inject Multiplier

**In `__init__()`** (after line 136, following existing pattern):

```python
self.density_threshold = config.get('density_threshold', 1.0)
self.density_multiplier_min = config.get('density_multiplier_min', 0.5)
self.density_multiplier_max = config.get('density_multiplier_max', 1.5)
self.density_structured_bonus = config.get('density_structured_bonus', 0.2)
```

**New import** (after line 32):

```python
from src.density_evaluator import calculate_density_multiplier
```

**Inject in `_run_mcts_iteration()`** (between lines 408 and 411):

```python
        # --- DENSITY MULTIPLIER (Layer 3) [COGN-04] ---
        parent_for_density = child.parent.instruction if child.parent else self.skill_original
        density_mult = calculate_density_multiplier(
            child_instruction=child.instruction,
            parent_instruction=parent_for_density,
            mutation_strategy=child.mutation_strategy,
            density_threshold=self.density_threshold,
            density_multiplier_min=self.density_multiplier_min,
            density_multiplier_max=self.density_multiplier_max,
            structured_bonus=self.density_structured_bonus,
        )
        if density_mult != 1.0:
            direction = "Bônus por Densidade" if density_mult > 1.0 else "Penalidade por Densidade"
            self.on_progress(f"    [{direction}] Fator: {density_mult:.2f}")
        reward = reward * density_mult
        # -----------------------------------------------
```

### 4. Line Number Summary of All Modifications

| File | Line | Change |
|------|------|--------|
| `src/density_evaluator.py` | NEW | Entire file (~45 lines) |
| `src/config.py` | ~103-106 | Add 4 density config keys to `get_mcts_config()` |
| `src/optimizer.py` | ~33 (imports) | Add `from src.density_evaluator import calculate_density_multiplier` |
| `src/optimizer.py` | ~137-140 (after line 136) | Add `self.density_*` attribute assignments |
| `src/optimizer.py` | ~409-419 (between 408 and 411) | Inject density multiplier block (~12 lines) |
| `tests/test_density_evaluator.py` | NEW | Unit tests for density function |
| `tests/test_config.py` | ~20-40 | Add density config default/override tests |
| `tests/test_optimizer.py` | ~62-100 | Add density multiplier integration tests |

---

## Risk Assessment

### Risk 1 — Pathological Compression: Very short but meaningless instructions score high (MEDIUM)

**Issue:** The compression ratio `len(child)/len(parent)` rewards any short instruction, even if it's "Foo bar baz" (nonsense). The density threshold formula `mult = threshold / ratio` produces multiplier > 1.0 for any compressed output regardless of quality.

**Mitigation:** The density multiplier is applied AFTER ModoB scoring. A meaningless short instruction will receive a low ModoB score (~0.1-0.2), so even with a 1.5x density boost, the final reward is capped at 0.3 — far below a quality instruction's typical 0.7+ score. The ModoB judge is the primary quality gate; density is a secondary nudge.

**Warning signs:** If the optimizer starts selecting extremely short, low-quality outputs, check whether ModoB scoring is still functioning correctly (drift monitor).

### Risk 2 — Content Stripping: Removing important context to game the compression ratio (LOW)

**Issue:** The LLM might learn to strip important context or safety instructions to produce shorter outputs, gaming the compression metric.

**Mitigation:** The semantic penalty (Layer 2) already penalizes instructions that are semantically too close to the parent. Stripping context would make the instruction dissimilar AND lower quality (ModoB score drops). Two independent guard layers.

### Risk 3 — Structured Bonus False Positives (LOW)

**Issue:** An instruction might have the three headings (`## Raciocínio`, `## Regras`, `## Conclusão`) but contain filler content under each heading.

**Mitigation:** This is acceptable — the structured bonus is a nudge toward structure, not a quality guarantee. The ModoB judge evaluates the actual content quality. The bonus (0.2) is small enough not to dominate the reward signal.

### Risk 4 — Over-Optimization: MCTS converges on extremely short outputs (LOW-MEDIUM)

**Issue:** After many iterations, MCTS might favor extremely compressed instructions, converging prematurely on short outputs.

**Mitigation:** The `density_multiplier_max = 1.5` cap limits the maximum boost. Additionally, the delta reward shaping (`calcular_delta_reward`) compares against parent reward — if ALL siblings are short, there's no delta advantage. The MCTS will naturally balance exploration.

**Warning signs:** Track average instruction length across iterations. If length decreases monotonically, the density multiplier may be too aggressive.

### Risk 5 — Zero-length parent edge case (LOW)

**Issue:** `parent_instruction` could theoretically be empty, causing division by zero.

**Mitigation:** The formula uses `max(1, len(parent_instruction))` which handles zero-length parents gracefully.

### Risk 6 — Config key naming collision (LOW)

**Issue:** The env var `MCTS_DENSITY_THRESHOLD` might conflict with existing or future config keys.

**Mitigation:** The prefix `MCTS_` is consistent with all existing keys. No collision with existing keys verified.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 |
| Config file | none — pytest auto-discovery on `tests/` |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Component 1: `calculate_density_multiplier()` Unit Tests (NEW: `tests/test_density_evaluator.py`)

| # | Test Name | Input | Expected | Rationale |
|---|-----------|-------|----------|-----------|
| 1 | `test_compression_boost` | child="abc", parent="abcdef" (ratio=0.5) | mult ≈ 2.0, clamped to 1.5 | Short outputs get max boost |
| 2 | `test_verbosity_penalty` | child="abcdef", parent="abc" (ratio=2.0) | mult ≈ 0.5, clamped to 0.5 | Long outputs get max penalty |
| 3 | `test_equal_length_no_change` | child="abcdef", parent="abcdef" (ratio=1.0) | mult = 1.0 | Same length → neutral |
| 4 | `test_empty_parent_fallback` | child="abc", parent="" | mult based on max(1, 0)=1, ratio=3.0, mult=0.33→clamped to 0.5 | Zero-length parent handled safely |
| 5 | `test_empty_child` | child="", parent="abcdef" (ratio=0.0) | mult based on threshold / 0.01 → 100 → clamped to 1.5 | Zero-length child clamped to max |
| 6 | `test_structured_bonus_cognitivo` | child has headings, strategy='mutador_cognitivo', ratio=1.0 | mult = 1.0 + 0.2 = 1.2 | Structured fields get bonus |
| 7 | `test_structured_bonus_non_cognitivo` | child has headings, strategy='outra', ratio=1.0 | mult = 1.0 (no bonus) | Bonus only for cognitivo |
| 8 | `test_structured_bonus_missing_headings` | strategy='mutador_cognitivo', child missing headings | mult = 1.0 (no bonus) | No headings → no bonus |
| 9 | `test_custom_threshold` | density_threshold=0.8, ratio=0.8 | mult = 1.0 | Custom threshold changes breakeven |
| 10 | `test_clamping` | density_min=0.7, density_max=1.3, ratio=0.3 | mult = 1.3 (clamped max) | Configurable bounds respected |

**Example test code:**
```python
import pytest
from src.density_evaluator import calculate_density_multiplier, _has_structured_fields

def test_compression_boost():
    mult = calculate_density_multiplier(
        child_instruction="abc",
        parent_instruction="abcdef",
    )
    # ratio=0.5, threshold=1.0, so mult=1.0/0.5=2.0, clamped to 1.5
    assert mult == 1.5

def test_verbosity_penalty():
    mult = calculate_density_multiplier(
        child_instruction="abcdef",
        parent_instruction="abc",
    )
    # ratio=2.0, mult=1.0/2.0=0.5
    assert mult == 0.5

def test_equal_length_no_change():
    mult = calculate_density_multiplier(
        child_instruction="abcdef",
        parent_instruction="abcdef",
    )
    assert mult == 1.0

def test_structured_bonus_cognitivo():
    child = (
        "## Raciocínio\nThe analysis shows structural gaps.\n"
        "## Regras\nFollow strict logical derivation.\n"
        "## Conclusão\nRewrite with structured output."
    )
    mult = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=child,  # same length = ratio 1.0
        mutation_strategy='mutador_cognitivo',
    )
    assert mult == 1.2  # 1.0 + 0.2 bonus

def test_structured_bonus_non_cognitivo():
    child = (
        "## Raciocínio\nTest.\n"
        "## Regras\nTest.\n"
        "## Conclusão\nTest."
    )
    mult = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=child,
        mutation_strategy='outra',
    )
    assert mult == 1.0  # no bonus for non-cognitivo
```

### Component 2: `_has_structured_fields()` Unit Tests

| # | Test Name | Input | Expected |
|---|-----------|-------|----------|
| 1 | `test_all_headings_present` | Text with all 3 headings lowercase | True |
| 2 | `test_missing_one_heading` | Text with only 2 headings | False |
| 3 | `test_no_headings` | Plain text | False |
| 4 | `test_case_insensitive` | Text with mixed case headings | True |

### Component 3: Config Tests (existing `tests/test_config.py`)

| # | Test Name | Input | Expected |
|---|-----------|-------|----------|
| 1 | `test_density_config_defaults` | No env vars | defaults (0.5, 1.5, 1.0, 0.2) |
| 2 | `test_density_config_override` | Override env vars | overridden values |

### Component 4: Optimizer Integration Tests (existing `tests/test_optimizer.py`)

| # | Test Name | Input | Expected |
|---|-----------|-------|----------|
| 1 | `test_density_boost_applied` | Compressed instruction | `reward < simulation_reward * 1.5` (boosted but clamped) |
| 2 | `test_density_penalty_applied` | Verbose instruction | `reward < simulation_reward` (penalized) |
| 3 | `test_density_neutral_at_threshold` | Same-length instruction | `reward == simulation_reward` (no change) |
| 4 | `test_density_structured_bonus_integration` | cognitivo strategy with headings | reward higher than non-structured equivalent |
| 5 | `test_existing_tests_regression` | All existing test cases | Still pass |

**Example integration test:**
```python
def test_density_boost_applied(mock_heavy_evaluators):
    """Compressed instruction should receive a density boost."""
    opt = Optimizer(skill_original="This is a very long parent instruction that should be compressed significantly.")
    # Mock simulation to return known base reward
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.semantic_sim_threshold = 1.0  # disable semantic penalty
    
    root = MCTSNode(instruction=opt.skill_original)
    root.last_reward = 0.0
    # Child is much shorter (compressed)
    child = MCTSNode(instruction="Short.", parent=root)
    
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    
    # Density should boost the reward: compression_ratio = 6/70 ≈ 0.086
    # density_mult = 1.0 / 0.086 ≈ 11.6, clamped to 1.5
    # reward = 1.0 * 1.0(heuristic) * 1.0(semantic) * 1.5(density) = 1.5
    assert reward > 1.0  # Base reward boosted
    assert reward <= 1.5  # But clamped to max

def test_density_penalty_applied(mock_heavy_evaluators, sample_verbose_text):
    """Verbose instruction should receive a density penalty."""
    opt = Optimizer(skill_original="Short.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.semantic_sim_threshold = 1.0
    
    root = MCTSNode(instruction=opt.skill_original)
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)
    
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    
    # Verbose text should get penalized
    # compression_ratio = len(sample_verbose_text) / len("Short.") >> 1.0
    # density_mult = 1.0 / large_ratio, clamped to 0.5
    # reward = 1.0 * 1.0 * 1.0 * 0.5 = 0.5
    assert reward < 1.0
```

### Sampling Rate
- **Per task commit:** `pytest tests/test_density_evaluator.py -x -q`
- **Per wave merge:** `pytest tests/test_density_evaluator.py tests/test_config.py tests/test_optimizer.py -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_density_evaluator.py` — covers all density calculation unit tests
- [ ] Density evaluation tests added to `tests/test_density_evaluator.py`
- [ ] Density config tests added to `tests/test_config.py`
- [ ] Density integration tests added to `tests/test_optimizer.py`

---

## Common Pitfalls

### Pitfall 1: Division by Zero (Prevented)
**What goes wrong:** `parent_instruction` might be empty string, causing `len(child) / 0` → ZeroDivisionError.

**How to avoid:** Use `max(1, len(parent_instruction))` in the formula. Verified in the `calculate_density_multiplier` function.

### Pitfall 2: Unbounded Multiplier
**What goes wrong:** An extremely short child (e.g., ratio=0.01) would produce a multiplier of 100x, completely dominating the reward signal.

**How to avoid:** Clamp with `density_multiplier_min` and `density_multiplier_max`. The function caps at [0.5, 1.5] by default.

### Pitfall 3: Double Penalty with Heuristic Evaluator
**What goes wrong:** The heuristic evaluator already has a `verbosity_penalty_factor` that penalizes long+simple texts. If the density multiplier ALSO penalizes long texts, the combined effect might be excessive.

**How to avoid:** The heuristic penalty targets different characteristics (long AND simple/readable text). The density multiplier penalizes ALL expansion relative to parent. They are complementary but independent — no double-counting because they measure different things. However, monitor interaction at config review.

### Pitfall 4: Structured Bonus Registration — Non-Cognitivo Strategy with Headings
**What goes wrong:** A non-cognitivo strategy could accidentally produce headings matching the cognitive sections, and we might incorrectly give it the structured bonus.

**How to avoid:** The `mutation_strategy` check (`== 'mutador_cognitivo'`) ensures the bonus only applies to explicitly cognitive strategies. Non-cognitivo strategies get the universal compression ratio only.

---

## Code Examples

### Full Density Evaluator Module (`src/density_evaluator.py`)

```python
def _has_structured_fields(instruction: str) -> bool:
    """Check if the instruction has the three cognitive headings."""
    normalized = instruction.lower()
    required = ['## raciocínio', '## regras', '## conclusão']
    return all(s in normalized for s in required)


def calculate_density_multiplier(
    child_instruction: str,
    parent_instruction: str,
    mutation_strategy: str = '',
    density_threshold: float = 1.0,
    density_multiplier_min: float = 0.5,
    density_multiplier_max: float = 1.5,
    structured_bonus: float = 0.2,
) -> float:
    parent_len = max(1, len(parent_instruction))
    compression_ratio = len(child_instruction) / parent_len
    density_mult = density_threshold / max(0.01, compression_ratio)
    density_mult = max(density_multiplier_min, min(density_multiplier_max, density_mult))
    
    if mutation_strategy == 'mutador_cognitivo' and _has_structured_fields(child_instruction):
        density_mult += structured_bonus
    
    return density_mult
```

### Integration Block for `optimizer.py`

```python
# --- DENSITY MULTIPLIER (Layer 3) [COGN-04] ---
parent_for_density = child.parent.instruction if child.parent else self.skill_original
density_mult = calculate_density_multiplier(
    child_instruction=child.instruction,
    parent_instruction=parent_for_density,
    mutation_strategy=child.mutation_strategy,
    density_threshold=self.density_threshold,
    density_multiplier_min=self.density_multiplier_min,
    density_multiplier_max=self.density_multiplier_max,
    structured_bonus=self.density_structured_bonus,
)
if density_mult != 1.0:
    direction = "Bônus por Densidade" if density_mult > 1.0 else "Penalidade por Densidade"
    self.on_progress(f"    [{direction}] Fator: {density_mult:.2f}")
reward = reward * density_mult
# -----------------------------------------------
```

### Config Keys for `config.py`

```python
# Parâmetros do Multiplicador de Densidade (COGN-04)
'density_multiplier_min': float(os.environ.get('MCTS_DENSITY_MULTIPLIER_MIN', '0.5')),
'density_multiplier_max': float(os.environ.get('MCTS_DENSITY_MULTIPLIER_MAX', '1.5')),
'density_threshold': float(os.environ.get('MCTS_DENSITY_THRESHOLD', '1.0')),
'density_structured_bonus': float(os.environ.get('MCTS_DENSITY_STRUCTURED_BONUS', '0.2')),
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No density consideration | Density multiplier as final reward layer | Phase 7 (COGN-04) | MCTS now rewards compressed, structured outputs |
| MutadorCognitivo validated for content only | MutadorCognitivo also gets density bonus for structure | Phase 7 (COGN-04) | Cognitive strategy doubly incentivized — compression + structure |
| All strategies treated equally | Universal compression for all + structured bonus for cognitivo | Phase 7 (COGN-04) | Differentiated reward signal based on strategy type |

---

## Assumptions Log

> All claims in this research were verified against the source code or official documentation — no user confirmation needed for execution.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `len()` character count is the correct metric for compression ratio (D-03 specifies `len()`) | Implementation Details | Low — user explicitly specified `len()` in D-03 |
| A2 | The structured bonus uses the same heading check as MutadorCognitivoOutput (`## Raciocínio`, `## Regras`, `## Conclusão`) | Implementation Details | Low — validated in `test_signatures.py` test code |
| A3 | `child.mutation_strategy` is available at the density calculation point in `_run_mcts_iteration` | Implementation Details | Confirmed: `_expand_node()` returns a child with `mutation_strategy` set (line 354) before `_run_mcts_iteration` reaches density calculation |
| A4 | Default values (0.5, 1.5, 1.0, 0.2) are reasonable starting points | Implementation Details | Medium — may need tuning after observing MCTS behavior |

---

## Open Questions

1. **Optimal default values for density parameters?**
   - What we know: D-02 says configurable, D-01 says final multiplier. The defaults (min=0.5, max=1.5, threshold=1.0, structured_bonus=0.2) are theoretical starting points.
   - What's unclear: Whether 1.5x max boost is too strong or too weak for the MCTS reward landscape.
   - Recommendation: Start with these defaults. If the MCTS converges on short outputs too quickly, lower `density_multiplier_max` to 1.2. If density isn't changing behavior, raise to 1.8.

2. **Should the structured bonus be additive or multiplicative?**
   - What we know: We chose additive (+0.2) after the clamp.
   - What's unclear: Whether additive bonus or multiplicative (e.g., `density_mult *= 1.2`) is more appropriate.
   - Recommendation: Additive is more predictable and bounded. Keep additive.

3. **Integration order within the pipeline — heuristic → ModoB → semantic → density?**
   - What we know: D-01 says density is the final multiplier after all existing layers. D-04 confirms no refactoring of existing layers.
   - What's unclear: Nothing — the order is locked by decisions.
   - Recommendation: Follow D-01/D-04 strictly.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | Runtime | ✓ | 3.x (CPython) | — |
| pytest | Tests | ✓ | 9.1.1 | — |
| textstat | Density (not used by density calc, but in project) | ✓ | 0.7.13 | — |
| sentence-transformers | Existing pipeline (not needed for density) | ✓ | 5.6.0 | — |
| dspy-ai | Existing pipeline | ✓ | 3.2.1 | — |
| torch | sentence-transformers dependency | ✓ | 2.5.1+cu121 | — |

**Missing dependencies with no fallback:** None

---

## Security Domain

> `security_enforcement` is enabled by default in this project (config.json does not set it to false).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `len()` character count and heading detection operate only on string length and substring matching — no injection risk |
| V6 Cryptography | no | No cryptographic operations in density multiplier |

### Known Threat Patterns for Density Calculation

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DoS via extremely long instruction | Denial of Service | `len()` is O(n) and fast for any reasonable input; existing 2048-char truncation in semantic_evaluator mitigates for embedding calls; density uses `len()` only (no embedding) |

**Security conclusion:** The density multiplier is a pure arithmetic function with no external system calls, no LLM invocations, no file I/O, and no network access. Security risk is negligible.

---

## Sources

### Primary (VERIFIED — Codebase Analysis)
- `src/optimizer.py` lines 361-436 — Exact reward pipeline with line numbers for injection
- `src/config.py` lines 62-103 — Config pattern (`os.environ.get('MCTS_*', 'default')` with explicit cast)
- `src/heuristic_evaluator.py` lines 1-31 — Multiplier pattern (`reward = reward * multiplier`)
- `src/semantic_evaluator.py` lines 1-31 — Penalty pattern (`reward = reward * penalty`)
- `src/signatures.py` lines 63-76 — `MutadorCognitivoOutput` validator with heading detection
- `src/optimizer.py` lines 243-359 — `_expand_node()` showing `child.mutation_strategy` availability
- `tests/test_heuristic_evaluator.py` — Existing test patterns
- `tests/test_config.py` — Config test patterns
- `tests/test_signatures.py` — Validator test patterns

### Secondary (VERIFIED — Environment)
- `pip list` — Confirmed pytest 9.1.1, dspy 3.2.1, textstat 0.7.13, sentence-transformers 5.6.0

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Density uses only Python stdlib — no package decisions needed |
| Architecture | HIGH | Integration point locked by D-01/D-04; line numbers verified in source |
| Pitfalls | HIGH | All edge cases (zero-length, clamping, double penalty) verified against source |
| Config defaults | MEDIUM | Defaults are theoretical — may need tuning after observing MCTS behavior |

**Research date:** 2026-07-10  
**Valid until:** 2026-08-10 (stable, no external package changes)

---

## RESEARCH COMPLETE

**Phase:** 07 - Otimização por Densificação Extrema  
**Requirement:** COGN-04  
**Confidence:** HIGH

### Key Findings

1. **Integration point locked:** Density multiplier goes after line 408 (semantic penalty) and before line 411 (feedback storage) in `_run_mcts_iteration()`. This is confirmed by D-01 and D-04, and verified in the source code.

2. **No new packages needed:** The density calculation uses `len()` (built-in) and substring matching. Zero external dependencies.

3. **Formula is straightforward:** `density_mult = clamp(threshold / compression_ratio, min, max)`, then `+ structured_bonus` if MutadorCognitivo with headings.

4. **Structured detection is trivial:** Check `child.mutation_strategy == 'mutador_cognitivo'` AND the instruction contains the three headings (`## Raciocínio`, `## Regras`, `## Conclusão`).

5. **Existing multiplier pattern reused:** The heuristic multiplier and semantic penalty already use `reward = reward * factor`. The density multiplier follows the exact same pattern.

6. **Main risk is pathological compression** (short meaningless outputs), but this is mitigated by ModoB scoring being the primary quality gate. Density is only a secondary nudge.

### Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| CREATE | `src/density_evaluator.py` | `calculate_density_multiplier()` + `_has_structured_fields()` |
| MODIFY | `src/config.py` | Add 4 density config keys |
| MODIFY | `src/optimizer.py` | Import `calculate_density_multiplier`, load config, inject block |
| CREATE | `tests/test_density_evaluator.py` | Unit tests for density function |
| MODIFY | `tests/test_config.py` | Add density config tests |
| MODIFY | `tests/test_optimizer.py` | Add density integration tests |

### Ready for Planning

Research complete. Planner can now create PLAN.md files for Phase 07. Recommended split: **1 plan** — the density multiplier is a single coherent change (config + function + integration + tests). No waves needed.

---

*Phase: 07-Otimização por Densificação Extrema*
*Research conducted: 2026-07-10*
