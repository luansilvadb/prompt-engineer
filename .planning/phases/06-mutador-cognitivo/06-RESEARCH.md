# 06-RESEARCH.md — Phase 06: Mutador Cognitivo

**Requirement:** COGN-01  
**Researched:** 2026-07-10  
**Source files read:** `src/signatures.py`, `src/mutation_strategies/registry.py`, `src/mutation_strategies/bandit.py`, `src/mutation_strategies/api.py`, `src/mutations.py`, `src/optimizer.py`, `src/config.py`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/phases/06-mutador-cognitivo/06-CONTEXT.md`, `tests/conftest.py`, `tests/test_optimizer.py`

---

## Technical Approach

### What COGN-01 Requires

COGN-01 states: *"Mutador Cognitivo injeta estruturas de raciocínio lógico (ex: blocos pydantic) nas skills criadas durante a mutação."*

The four decisions from CONTEXT.md define the full implementation surface:

| Decision | Action |
|----------|--------|
| D-01 | Create `MutadorCognitivoAgent` as a new DSPy Signature, inheriting `SelfReflectiveAgent`'s fields + adding `raciocinio_estruturado: str` OutputField. `SelfReflectiveAgent` stays untouched. |
| D-02 | `raciocinio_estruturado` is Pydantic-validated: mandatory sections `premissas`, `deducoes`, `conclusao`. `nova_instrucao` must contain `## Raciocínio`, `## Regras`, `## Conclusão` headings. |
| D-03 | `MutadorCognitivo` is registered as a hardcoded seed in `StrategyRegistry.__init__`. `optimizer.py` routes to `MutadorCognitivoAgent` when bandit selects this strategy key. |
| D-04 | `MutadorCognitivo` receives prior boosting via `load_priors()` with positive virtual counts, configurable in `config.py`. |

### Architecture Overview

The integration touches **4 components** in a fan-out pattern:

```
StrategyRegistry.__init__()          # D-03: seed registration
       ↓
MutationBandit.__init__()           # picks up seed from registry.get_all_keys()
       ↓
Optimizer.__init__() → load_priors() # D-04: inject virtual counts
       ↓
_expand_node()                       # D-03: routing intercept → MutadorCognitivoAgent
       ↓
signatures.py (new classes)          # D-01 + D-02: Signature + Pydantic validator
```

The MCTS flow remains fully unmodified in its tree logic (selection, backpropagation, reward shaping). The only mutation is inside `_expand_node()` where the agent call is routed.

---

## Implementation Details

### 1. `src/signatures.py` — Current State

**`SelfReflectiveAgent`** (lines 23–30) — exact fields:
```python
class SelfReflectiveAgent(dspy.Signature):
    """Analisa uma instrução avaliada..."""
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField(desc="...")
    estrategia_mutacao: str = dspy.InputField(desc="...")
    critica: str = dspy.OutputField(desc="...")
    nova_instrucao: str = dspy.OutputField(desc="...")
```

**`GeracaoSkill`** (lines 5–13) — Pydantic validator pattern used in the project:
```python
class GeracaoSkill(BaseModel):
    critica: str = Field(description="...")
    nova_instrucao: str = Field(description="...")

    @field_validator('nova_instrucao')
    def validar_tamanho_instrucao(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("...")
        return v
```

**`Avaliacao`** (lines 32–56) — more complex multi-field validator pattern:
```python
@field_validator('nota_clareza', 'nota_formatacao', ..., mode='before')
@classmethod
def validar_nota(cls, v):
    import re
    # coercion + range validation
    ...
    return v_float
```

**Existing imports at top of file (line 3):**
```python
from pydantic import BaseModel, Field, field_validator
```

**What must be added to `signatures.py`:**

```python
class RaciocinioCognitivo(BaseModel):
    """Estrutura obrigatória do raciocínio lógico gerado pelo MutadorCognitivo."""
    premissas: str = Field(description="Premissas extraídas do feedback e da instrução atual.")
    deducoes: str = Field(description="Deduções e implicações lógicas derivadas das premissas.")
    conclusao: str = Field(description="Conclusão acionável — o que a nova instrução DEVE fazer diferente.")

    @field_validator('premissas', 'deducoes', 'conclusao')
    @classmethod
    def validar_campo_preenchido(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError("Campo obrigatório do raciocínio estruturado está vazio ou genérico.")
        return v

class MutadorCognitivoAgent(dspy.Signature):
    """Analisa a instrução com derivação lógica estruturada obrigatória. OBRIGATÓRIO: preencha
    raciocinio_estruturado com premissas, deduções e conclusão explícitas antes de reescrever.
    A nova instrução DEVE incluir as seções ## Raciocínio, ## Regras, ## Conclusão derivadas do raciocínio."""
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField(desc="Feedback detalhado do avaliador explicando os motivos da nota.")
    estrategia_mutacao: str = dspy.InputField(desc="Estratégia de mutação a ser aplicada nesta iteração.")
    critica: str = dspy.OutputField(desc="Análise do feedback e proposta de nova abordagem.")
    raciocinio_estruturado: str = dspy.OutputField(
        desc="Derivação lógica obrigatória com campos: premissas | deducoes | conclusao. Não pode ser genérico."
    )
    nova_instrucao: str = dspy.OutputField(
        desc="A nova skill reescrita em Markdown. DEVE conter ## Raciocínio, ## Regras, ## Conclusão derivados do raciocinio_estruturado."
    )
```

**DSPy Signature inheritance caveat (critical):** DSPy Signatures do NOT support Python-style class inheritance in the traditional OOP sense for field composition. The correct pattern is to **redeclare all fields** from the parent in the child class. `MutadorCognitivoAgent` must explicitly repeat all 4 input fields and both output fields from `SelfReflectiveAgent`, then add `raciocinio_estruturado`. Attempting `class MutadorCognitivoAgent(SelfReflectiveAgent)` may work in newer DSPy but behavior is version-dependent — explicit field redeclaration is the safe path.

**`nova_instrucao` section validator** — must also validate the 3 mandatory Markdown headings:
```python
@field_validator('nova_instrucao')
@classmethod  
def validar_secoes_cognitivas(cls, v):
    required = ['## Raciocínio', '## Regras', '## Conclusão']
    missing = [s for s in required if s not in v]
    if missing:
        raise ValueError(f"nova_instrucao deve conter as seções: {missing}")
    if len(v.strip()) < 50:
        raise ValueError("nova_instrucao muito curta.")
    return v
```

> Note: This validator lives on a separate Pydantic model `MutadorCognitivoOutput` wrapping the DSPy output. DSPy `OutputField` doesn't natively run Pydantic validators — the validation must happen after `.nova_instrucao` is read from the DSPy prediction inside `_expand_node()`.

---

### 2. `src/mutation_strategies/registry.py` — Seed Registration

**`StrategyRegistry.add_strategy(key, name, prompt)` signature (line 53):**
```python
def add_strategy(self, key: str, name: str, prompt: str):
    self.strategies[key] = {'name': name, 'prompt': prompt}
    self.save()
```

**`_load()` reads from `src/outputs/strategies/discovered_strategies.json`** (line 34–41).

**Strategy key constant to use:** `'mutador_cognitivo'` (snake_case, consistent with auto-discover key format).

**Where to inject the seed in `__init__`** (after `self._load()` on line 28):
```python
def __init__(self):
    self.strategies: Dict[str, Dict[str, str]] = {}
    self._load()
    self._seed_hardcoded_strategies()  # NEW

def _seed_hardcoded_strategies(self):
    """Register built-in strategies that must always exist."""
    COGNITIVO_KEY = 'mutador_cognitivo'
    if COGNITIVO_KEY not in self.strategies:
        self.add_strategy(
            key=COGNITIVO_KEY,
            name='Mutador Cognitivo',
            prompt=(
                "Aplique derivação lógica estruturada obrigatória. "
                "Antes de reescrever, derive explicitamente: "
                "(1) Premissas — o que o feedback revela sobre a instrução atual; "
                "(2) Deduções — implicações lógicas sobre o que precisa mudar; "
                "(3) Conclusão — a regra arquitetural que a nova instrução deve implementar. "
                "A nova instrução DEVE conter as seções ## Raciocínio, ## Regras, ## Conclusão."
            )
        )
```

**Idempotency check (`if COGNITIVO_KEY not in self.strategies`)** is critical — the registry persists to JSON, so on restart the key already exists.

---

### 3. `src/mutation_strategies/bandit.py` — Prior Boosting

**`load_priors(strategy_stats)` exact signature (line 44–49):**
```python
def load_priors(self, strategy_stats: Dict[str, Dict[str, float]]):
    for strategy, stats in strategy_stats.items():
        self._ensure_key(strategy)
        virtual_count = min(int(stats['count'] * 0.5), 10)
        self._counts[strategy] += virtual_count
        self._rewards[strategy] += stats.get('mean_delta', 0.0) * virtual_count
```

**Existing call in `optimizer.py` (lines 146–149):**
```python
strategy_stats = self.experience_store.get_strategy_stats()
if strategy_stats:
    self.mutation_bandit.load_priors(strategy_stats)
```

**To inject priors for `MutadorCognitivo` regardless of ExperienceStore** — a separate call AFTER the existing experience store call:
```python
cognitivo_prior = {
    'mutador_cognitivo': {
        'count': config.get('cognitivo_prior_count', 4),
        'mean_delta': config.get('cognitivo_prior_mean_delta', 0.05)
    }
}
self.mutation_bandit.load_priors(cognitivo_prior)
```

**Virtual count formula:** `virtual_count = min(int(4 * 0.5), 10) = 2`. Gives 2 virtual pulls with 0.10 virtual reward — competitive but not dominant.

**Re-initialization risk:** Bandit is re-initialized fresh on every `Optimizer.__init__()` — `_counts` and `_rewards` reset to zero before any `load_priors()`. Prior injection is idempotent per-session. Confirmed safe.

---

### 4. `src/optimizer.py` — Strategy Routing

**Current agent instantiation (line 139):**
```python
self.agent = dspy.ChainOfThought(SelfReflectiveAgent)
```

**Where routing must happen — inside `_expand_node()` (lines 232–331):**

Strategy key resolved at line 234: `strategy = self.mutation_bandit.select()`

Agent call at line 292: `predicao = self.agent(...)`

**Routing intercept pattern:**
```python
# In Optimizer.__init__(), after line 139:
self.agent_cognitivo = dspy.ChainOfThought(MutadorCognitivoAgent)

# In _expand_node(), replace the agent call with:
COGNITIVO_KEY = 'mutador_cognitivo'
if strategy == COGNITIVO_KEY:
    predicao = self.agent_cognitivo(
        instrucao_anterior=leaf.instruction,
        nota_anterior=nota,
        feedback_juiz=feedback_completo,
        estrategia_mutacao=strategy_prompt,
    )
    # Post-hoc Pydantic validation of raciocinio_estruturado
    try:
        _validate_raciocinio(predicao.raciocinio_estruturado)
    except Exception as e:
        self.on_error(f'[!] raciocinio_estruturado inválido: {e}')
    critica = predicao.critica
    nova_instrucao = predicao.nova_instrucao
else:
    predicao = self.agent(
        instrucao_anterior=leaf.instruction,
        nota_anterior=nota,
        feedback_juiz=feedback_completo,
        estrategia_mutacao=strategy_prompt,
    )
    critica = predicao.critica
    nova_instrucao = predicao.nova_instrucao
```

**`candidata` extraction (line 298):** `candidata = predicao.nova_instrucao` — works identically for `MutadorCognitivoAgent`.

**`__DISCOVER__` interaction:** The `__DISCOVER__` branch resolves before any agent call — no conflict.

---

### 5. `src/config.py` — New Config Knobs

**Existing pattern:** All values from `os.environ.get('KEY', 'default')` inside `get_mcts_config()`. Returns a plain `dict`.

**What to add to `get_mcts_config()`:**
```python
# Prior boosting para MutadorCognitivo (COGN-01)
'cognitivo_prior_count': int(os.environ.get('MCTS_COGNITIVO_PRIOR_COUNT', '4')),
'cognitivo_prior_mean_delta': float(os.environ.get('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', '0.05')),
```

**Default rationale:** `count=4` → 2 virtual pulls. `mean_delta=0.05` → marginal positive bias. Nudges UCB1 toward early exploration without freezing it there.

---

## Risk Assessment

### Risk 1 — DSPy Signature Inheritance (HIGH)
**Issue:** DSPy's `Signature` metaclass may not properly merge `InputField`/`OutputField` declarations from parent classes depending on DSPy version. Some versions support field inheritance; others silently drop parent fields.  
**Evidence:** No existing code in this project inherits from a DSPy Signature — all are standalone classes.  
**Mitigation:** Redeclare ALL fields from `SelfReflectiveAgent` explicitly in `MutadorCognitivoAgent`. Do not rely on Python MRO for field resolution.

### Risk 2 — Pydantic validation cannot run directly on DSPy OutputField (MEDIUM)
**Issue:** DSPy does not pass `OutputField` values through Pydantic validators — it just stores strings in a `Prediction` object.  
**Evidence:** `GeracaoSkill` is a standalone Pydantic model, not wired to any DSPy Signature.  
**Mitigation:** Define `RaciocinioCognitivo(BaseModel)` as a standalone validator and call it explicitly inside `_expand_node()` after extracting the DSPy prediction.

### Risk 3 — `raciocinio_estruturado` format is LLM-dependent (MEDIUM)
**Issue:** The LLM will produce `raciocinio_estruturado` as free-form text. Expecting JSON without explicit DSPy output constraints may result in unparseable strings.  
**Mitigation:** Design `raciocinio_estruturado` as a Markdown block with labeled sections (`**Premissas:**`, `**Deduções:**`, `**Conclusão:**`). Validation checks for presence of these labels via string search.

### Risk 4 — Seed registration writes to JSON on first run (LOW)
**Issue:** `add_strategy()` calls `save()` which writes to the strategies JSON file.  
**Mitigation:** The guard `if COGNITIVO_KEY not in self.strategies` after `_load()` is sufficient.

### Risk 5 — Prior boosting additive across restarts (LOW — CONFIRMED SAFE)
**Issue:** Each restart calls the hardcoded prior injection.  
**Resolution:** Bandit is re-initialized fresh on every `Optimizer.__init__()` — `_counts` and `_rewards` reset to zero before any `load_priors()`. No cross-session contamination.

### Risk 6 — `nova_instrucao` section validator false negatives (LOW)
**Issue:** LLM may write headings with different accent/casing.  
**Mitigation:** Use `.lower()` normalization or make the validator a warning (log only) for the first iteration — soft enforcement fallback.

---

## Validation Architecture

### Component 1: `MutadorCognitivoAgent` DSPy Signature (Unit)
- Instantiate `dspy.ChainOfThought(MutadorCognitivoAgent)` without calling LLM. Assert `output_fields` contains `'critica'`, `'raciocinio_estruturado'`, `'nova_instrucao'`.
- Assert `input_fields` contains `'instrucao_anterior'`, `'nota_anterior'`, `'feedback_juiz'`, `'estrategia_mutacao'`.

### Component 2: `RaciocinioCognitivo` Pydantic Validator (Unit)
- Happy path: all three fields populated → must not raise.
- Empty field: `premissas=""` → must raise `ValidationError`.
- Too short: any field with len < 10 → must raise `ValidationError`.
- `nova_instrucao` missing `## Raciocínio` → must fail validation.
- `nova_instrucao` with all 3 sections → must pass.

### Component 3: `StrategyRegistry` Seed Registration (Unit)
- Instantiate with empty/absent JSON. Assert `'mutador_cognitivo' in registry.get_all_keys()`.
- Idempotency: instantiate twice. Assert only one `mutador_cognitivo` entry. Assert `save()` not called a second time (mock `save`).
- `registry.get_prompt('mutador_cognitivo')` returns non-empty string containing "premissas".
- `registry.get_name('mutador_cognitivo')` returns `'Mutador Cognitivo'`.

### Component 4: `MutationBandit` Prior Boosting (Unit)
- Load priors with `count=4, mean_delta=0.05`. Assert `_counts['mutador_cognitivo'] == 2` and `_rewards['mutador_cognitivo'] == 0.10`.
- Re-initialize `MutationBandit()` — assert counts reset to 0 before `load_priors()`.
- UCB1 selection: after prior boost with all other arms at 0, assert `mutador_cognitivo` is selected within first N rounds.

### Component 5: `optimizer.py` Strategy Routing (Unit)
- Mock `mutation_bandit.select()` → `'mutador_cognitivo'`. Mock `agent_cognitivo`. Run `_expand_node()`. Assert `agent_cognitivo` was called; `self.agent` was NOT.
- Non-cognitivo strategy: assert `self.agent` called; `agent_cognitivo` NOT called.
- Regression guard: existing `test_optimizer_layer1_hard_pruning` and `test_optimizer_layer2_penalty_multiplier` must still pass.

### Component 6: `config.py` New Keys (Unit)
- With env `MCTS_COGNITIVO_PRIOR_COUNT=6`, `MCTS_COGNITIVO_PRIOR_MEAN_DELTA=0.1`: assert returned dict has those values.
- Without env vars: assert defaults `4` and `0.05`.

### Component 7: Integration Smoke Test (Integration, no LLM)
- Initialize `Optimizer(skill_original="Test skill")` with all LLM calls mocked. Assert:
  1. `'mutador_cognitivo'` exists in `self.mutation_bandit._counts`.
  2. `self.mutation_bandit._counts['mutador_cognitivo'] > 0`.
  3. `self.agent_cognitivo` attribute exists.
- Force bandit to select `mutador_cognitivo` (patch `select()`). Run one `_run_mcts_iteration()`. Assert a child node was created with `mutation_strategy == 'mutador_cognitivo'`.

---

## RESEARCH COMPLETE

**Summary of concrete facts found:**

1. `SelfReflectiveAgent` has 4 InputFields + 2 OutputFields. `MutadorCognitivoAgent` must redeclare all 6 + add `raciocinio_estruturado` as the 3rd OutputField.
2. Pydantic validation pattern: standalone `BaseModel` with `@field_validator` + `@classmethod`. NOT automatically wired to DSPy Predictions — explicit post-call validation required.
3. `StrategyRegistry.add_strategy(key, name, prompt)` is the exact registration interface. Call from `_seed_hardcoded_strategies()` inside `__init__`, guarded by `if key not in self.strategies`.
4. `MutationBandit.load_priors({'mutador_cognitivo': {'count': 4, 'mean_delta': 0.05}})` injects 2 virtual pulls with 0.10 virtual reward. Bandit resets clean on each `Optimizer.__init__()`.
5. Strategy routing intercept belongs inside `_expand_node()` after `strategy = self.mutation_bandit.select()`. Second module `self.agent_cognitivo = dspy.ChainOfThought(MutadorCognitivoAgent)` instantiated in `Optimizer.__init__()`.
6. Two new config keys: `cognitivo_prior_count` (int, default 4) and `cognitivo_prior_mean_delta` (float, default 0.05) added to `get_mcts_config()`.
7. Biggest risk: DSPy field inheritance — mitigate by redeclaring all fields explicitly. Second risk: Pydantic validators don't auto-fire on DSPy Predictions — mitigate by post-call explicit validation.

---
*Phase: 06-mutador-cognitivo*
*Research conducted: 2026-07-10*
