# Phase 06: Mutador Cognitivo - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 10 (4 modified source + 5 new tests + 1 extended test)
**Analogs found:** 10 / 10

> All analogs are existing files in this repo. New classes/functions are co-located with their analogs (same file), so "closest analog" usually points to the sibling class the new code must mirror.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/signatures.py` (+`RaciocinioCognitivo`, +`MutadorCognitivoAgent`, +`_validate_raciocinio`) | model / signature | transform | `SelfReflectiveAgent` + `GeracaoSkill` + `Avaliacao` (same file) | exact |
| `src/config.py` (+2 keys in `get_mcts_config`) | config | request-response | `get_mcts_config()` (same function) | exact |
| `src/mutation_strategies/registry.py` (+`_seed_hardcoded_strategies`) | store | CRUD | `StrategyRegistry.__init__` + `add_strategy` (same class) | exact |
| `src/optimizer.py` (+import, +`agent_cognitivo`, +prior boost, +routing in `_expand_node`) | controller | request-response / transform | `Optimizer.__init__` + `_expand_node` (same file) | exact |
| `tests/test_signatures.py` (NEW) | test | transform | `tests/test_heuristic_evaluator.py` + `tests/conftest.py` | role-match |
| `tests/test_registry.py` (NEW) | test | CRUD | `tests/test_optimizer.py` + `tests/conftest.py` | role-match |
| `tests/test_bandit.py` (NEW) | test | transform | `tests/test_optimizer.py` | role-match |
| `tests/test_config.py` (NEW) | test | request-response | `tests/test_heuristic_evaluator.py` | role-match |
| `tests/test_optimizer_integration.py` (NEW) | test (integration) | request-response | `tests/test_optimizer.py` | exact |
| `tests/test_optimizer.py` (EXTEND) | test | request-response | self (existing tests in same file) | exact |

## Pattern Assignments

### `src/signatures.py` — model / signature, transform

**Analog:** `SelfReflectiveAgent` (lines 23–30) for the DSPy Signature; `GeracaoSkill` (lines 5–13) + `Avaliacao` (lines 32–56) for the Pydantic validator pattern. All three live in the same file — new classes are appended alongside them.

**Imports pattern** (line 1–3, already present — no change needed):
```python
import dspy
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
```

**DSPy Signature pattern** (lines 23–30) — `MutadorCognitivoAgent` redeclares ALL 4 InputFields + 2 OutputFields from `SelfReflectiveAgent` and adds `raciocinio_estruturado` as a 3rd OutputField (RESEARCH Risk 1: do NOT rely on class inheritance):
```python
class SelfReflectiveAgent(dspy.Signature):
    """Analisa uma instrução avaliada. OBRIGATÓRIO: ..."""
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField(desc="Feedback detalhado do avaliador explicando os motivos da nota.")
    estrategia_mutacao: str = dspy.InputField(desc="Estratégia de mutação a ser aplicada nesta iteração. Siga rigorosamente a diretriz.")
    critica: str = dspy.OutputField(desc="Análise do feedback e proposta de qual nova abordagem testar (proibido dizer que está perfeito).")
    nova_instrucao: str = dspy.OutputField(desc="A nova skill reescrita e otimizada, formatada em Markdown.")
```

**Pydantic validator pattern — single field** (lines 5–13) — `RaciocinioCognitivo` follows this `BaseModel` + `@field_validator` shape for the `premissas`/`deducoes`/`conclusao` mandatory-content checks:
```python
class GeracaoSkill(BaseModel):
    critica: str = Field(description="Análise do feedback ...")
    nova_instrucao: str = Field(description="A nova skill reescrita ...")

    @field_validator('nova_instrucao')
    def validar_tamanho_instrucao(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("A nova instrução gerada é muito curta ...")
        return v
```

**Pydantic validator pattern — multi-field + classmethod** (lines 42–56) — for the multi-field validator on `RaciocinioCognitivo`, copy the `@field_validator(..., mode='before')` + `@classmethod` stack used by `Avaliacao.validar_nota`:
```python
    @field_validator('nota_clareza', 'nota_formatacao', 'nota_robustez', 'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade', mode='before')
    @classmethod
    def validar_nota(cls, v):
        import re
        if isinstance(v, str):
            match = re.search(r'\d+(?:\.\d+)?', v)
            if match:
                v = match.group(0)
        try:
            v_float = float(v)
        except (ValueError, TypeError):
            raise ValueError("A nota deve ser um número numérico.")
        if v_float < 0 or v_float > 100:
            raise ValueError("A nota deve estar rigorosamente entre 0 e 100.")
        return v_float
```

**Post-hoc validation function pattern** — `_validate_raciocinio(raciocinio_str)` is a standalone function (NOT a method on the DSPy Signature). DSPy `OutputField` values are plain strings on a `Prediction` and do not auto-run Pydantic (RESEARCH Risk 2). The function constructs `RaciocinioCognitivo` from the raw string and lets `ValidationError` propagate. Call it inside `_expand_node()` (see optimizer section).

---

### `src/config.py` — config, request-response

**Analog:** `get_mcts_config()` (lines 62–99). New keys are appended to the returned dict — same `os.environ.get('KEY', 'default')` + explicit `int(...)`/`float(...)` cast pattern.

**Existing config-knob pattern** (lines 68–99):
```python
def get_mcts_config() -> dict:
    load_dotenv()
    return {
        'gamma': float(os.environ.get('MCTS_GAMMA', '0.95')),
        'c_param': float(os.environ.get('MCTS_C_PARAM', '1.41')),
        # ... more keys ...
        'lexical_density_min': float(os.environ.get('MCTS_LEXICAL_DENSITY_MIN', '0.35')),
        'verbosity_penalty_factor': float(os.environ.get('MCTS_VERBOSITY_PENALTY_FACTOR', '0.85')),
    }
```

**To append** (mirror the `int(...)`/`float(...)` cast + `MCTS_` env-var prefix convention):
```python
'cognitivo_prior_count': int(os.environ.get('MCTS_COGNITIVO_PRIOR_COUNT', '4')),
'cognitivo_prior_mean_delta': float(os.environ.get('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', '0.05')),
```

---

### `src/mutation_strategies/registry.py` — store, CRUD

**Analog:** `StrategyRegistry.__init__` (lines 26–28) + `add_strategy` (lines 53–55) + `_load`/`save` (lines 34–51). New `_seed_hardcoded_strategies()` is called from `__init__` after `self._load()`.

**Init + load pattern** (lines 26–28):
```python
class StrategyRegistry:
    def __init__(self):
        self.strategies: Dict[str, Dict[str, str]] = {}
        self._load()
```

**Registration interface** (lines 53–55) — `add_strategy(key, name, prompt)` writes to dict and persists:
```python
    def add_strategy(self, key: str, name: str, prompt: str):
        self.strategies[key] = {'name': name, 'prompt': prompt}
        self.save()
```

**Seed registration pattern** — call `self._seed_hardcoded_strategies()` as the last line of `__init__` (after `self._load()`). The method must be **idempotent** (registry persists to JSON on `save()`, so on restart the key already exists). Guard with `if COGNITIVO_KEY not in self.strategies`:
```python
def _seed_hardcoded_strategies(self):
    COGNITIVO_KEY = 'mutador_cognitivo'
    if COGNITIVO_KEY not in self.strategies:
        self.add_strategy(
            key=COGNITIVO_KEY,
            name='Mutador Cognitivo',
            prompt="Aplique derivação lógica estruturada obrigatória ...",
        )
```

**Strategy key convention:** snake_case (`'mutador_cognitivo'`), consistent with auto-discover key format generated at `optimizer.py` line 252 (`re.sub(r'[^a-z0-9_]', '_', key_raw)`).

---

### `src/optimizer.py` — controller, request-response / transform

**Analog:** `Optimizer.__init__` (lines 138–149) for agent instantiation + prior loading; `_expand_node` (lines 232–331) for the routing intercept.

**Import pattern** (lines 24, 28–30) — add `MutadorCognitivoAgent` to the existing `from src.signatures import ...` line:
```python
from src.signatures import SelfReflectiveAgent, StrategyDiscoverer, funcao_de_recompensa, calcular_delta_reward, load_avaliador
# ...
from src.mutations import (
    MutationBandit, get_mutation_prompt, get_strategy_description, registry
)
```

**Agent instantiation pattern** (line 139) — new `self.agent_cognitivo` mirrors `self.agent`, added immediately after it:
```python
self.agent = dspy.ChainOfThought(SelfReflectiveAgent)
```
Add:
```python
self.agent_cognitivo = dspy.ChainOfThought(MutadorCognitivoAgent)
```

**Prior-boosting pattern** (lines 145–149) — existing experience-store load; the cognitivo prior is a SEPARATE `load_priors()` call AFTER it, unconditionally (not gated by `if strategy_stats:`), using values from `config`:
```python
strategy_stats = self.experience_store.get_strategy_stats()
if strategy_stats:
    self.mutation_bandit.load_priors(strategy_stats)
    self.on_progress(f'[*] Memória experiencial carregada: ...')
```
Add (reads `cognitivo_prior_count` / `cognitivo_prior_mean_delta` from `config` fetched at line 127):
```python
cognitivo_prior = {
    'mutador_cognitivo': {
        'count': config.get('cognitivo_prior_count', 4),
        'mean_delta': config.get('cognitivo_prior_mean_delta', 0.05),
    }
}
self.mutation_bandit.load_priors(cognitivo_prior)
```

**`load_priors` contract** (`bandit.py` lines 44–49) — formula `virtual_count = min(int(count * 0.5), 10)`; with `count=4` → 2 virtual pulls, `0.05 * 2 = 0.10` virtual reward:
```python
def load_priors(self, strategy_stats: Dict[str, Dict[str, float]]):
    for strategy, stats in strategy_stats.items():
        self._ensure_key(strategy)
        virtual_count = min(int(stats['count'] * 0.5), 10)
        self._counts[strategy] += virtual_count
        self._rewards[strategy] += stats.get('mean_delta', 0.0) * virtual_count
```

**Routing intercept pattern** (`_expand_node`, lines 234 + 291–298) — `strategy` resolved at line 234; the agent call at lines 291–298 is wrapped in a `try/except` inside a 3-attempt retry loop (lines 277–319). The intercept goes INSIDE that try block, branching on `strategy == 'mutador_cognitivo'`:
```python
strategy = self.mutation_bandit.select()          # line 234
# ...
try:
    predicao = self.agent(                         # line 292
        instrucao_anterior=leaf.instruction,
        nota_anterior=nota,
        feedback_juiz=feedback_completo,
        estrategia_mutacao=strategy_prompt,
    )
    candidata = predicao.nova_instrucao            # line 298
```
Replace the agent call with a branch:
```python
COGNITIVO_KEY = 'mutador_cognitivo'
if strategy == COGNITIVO_KEY:
    predicao = self.agent_cognitivo(
        instrucao_anterior=leaf.instruction,
        nota_anterior=nota,
        feedback_juiz=feedback_completo,
        estrategia_mutacao=strategy_prompt,
    )
    try:
        _validate_raciocinio(predicao.raciocinio_estruturado)
    except Exception as e:
        self.on_error(f'[!] raciocinio_estruturado inválido: {e}')
else:
    predicao = self.agent(
        instrucao_anterior=leaf.instruction,
        nota_anterior=nota,
        feedback_juiz=feedback_completo,
        estrategia_mutacao=strategy_prompt,
    )
candidata = predicao.nova_instrucao  # unchanged — both agents expose this field
```
Downstream `candidata`/`critica` extraction (lines 298–308) and the `MCTSNode` construction (lines 321–328, with `mutation_strategy=strategy`) work identically for both agents — no further changes needed.

**Error-handling pattern** (lines 313–319) — existing try/except + 3-attempt fallback to minimal variation. The post-hoc `_validate_raciocinio` exception is caught separately and logged via `self.on_error(...)`, NOT allowed to abort the retry loop (soft enforcement — RESEARCH Risk 6 mitigation).

**`__DISCOVER__` non-interaction** (lines 236–261) — the discover branch resolves `strategy` to a new key BEFORE the agent call, so it never reaches the cognitivo branch. No conflict.

---

### `tests/test_signatures.py` (NEW) — test, transform

**Analog:** `tests/test_heuristic_evaluator.py` (plain `def test_...()` functions, direct assert) + `tests/conftest.py` mock fixtures for heavy modules.

**Unit-test pattern** (`test_heuristic_evaluator.py` lines 1–14):
```python
import pytest
from src.heuristic_evaluator import evaluate_heuristics

def test_short_text_bypass():
    result = evaluate_heuristics("Curto e direto.")
    assert result["prune"] is False
    assert result["penalty_multiplier"] == 1.0
```

**Tests to write:**
- Happy path: `RaciocinioCognitivo(premissas=..., deducoes=..., conclusao=...)` → no raise.
- Empty/too-short field (<10 chars) → `pydantic.ValidationError`.
- `_validate_raciocinio` happy path + invalid string → raises.
- DSPy field introspection (no LLM call): instantiate `dspy.ChainOfThought(MutadorCognitivoAgent)`; assert `output_fields` contains `raciocinio_estruturado`, `input_fields` contains the 4 inputs. (Requires `mock_heavy_evaluators` fixture from conftest to avoid network config.)

**Import for ValidationError:**
```python
import pytest
from pydantic import ValidationError
from src.signatures import RaciocinioCognitivo, MutadorCognitivoAgent, _validate_raciocinio
```

---

### `tests/test_registry.py` (NEW) — test, CRUD

**Analog:** `tests/test_optimizer.py` (uses `mock_heavy_evaluators` fixture + `MagicMock`) + `conftest.py` fixtures.

**Test-with-fixture pattern** (`test_optimizer.py` lines 1–7):
```python
import pytest
from src.optimizer import Optimizer, MCTSNode
from unittest.mock import MagicMock

def test_optimizer_layer1_hard_pruning(mock_heavy_evaluators):
    opt = Optimizer(skill_original="foo")
    ...
```

**Tests to write** (idempotency + content assertions):
- Instantiate `StrategyRegistry()` with empty/absent JSON → `'mutador_cognitivo' in registry.get_all_keys()`.
- Idempotency: instantiate twice, mock `save()`, assert `save()` NOT called second time (key already present).
- `registry.get_prompt('mutador_cognitivo')` returns non-empty string containing "premissas".
- `registry.get_name('mutador_cognitivo')` returns `'Mutador Cognitivo'`.

**Import pattern:**
```python
import pytest
from unittest.mock import patch, MagicMock
from src.mutation_strategies.registry import StrategyRegistry
```

---

### `tests/test_bandit.py` (NEW) — test, transform

**Analog:** `tests/test_optimizer.py` (`MagicMock` + fixture pattern) + `bandit.py` `load_priors` (lines 44–49).

**Tests to write:**
- `load_priors({'mutador_cognitivo': {'count': 4, 'mean_delta': 0.05}})` → `_counts['mutador_cognitivo'] == 2`, `_rewards['mutador_cognitivo'] == 0.10`.
- Fresh `MutationBandit()` → counts reset to 0 before `load_priors()`.
- After prior boost (all other arms 0), `select()` returns `'mutador_cognitivo'` within first N rounds (UCB1 untried-first at `bandit.py` lines 80–82).

**Import pattern:**
```python
import pytest
from src.mutation_strategies.bandit import MutationBandit
```

---

### `tests/test_config.py` (NEW) — test, request-response

**Analog:** `tests/test_heuristic_evaluator.py` (direct function-call assertions).

**Tests to write** (env-var override + defaults):
- With `monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_COUNT', '6')` + `'MCTS_COGNITIVO_PRIOR_MEAN_DELTA', '0.1'` → `get_mcts_config()['cognitivo_prior_count'] == 6`, `['cognitivo_prior_mean_delta'] == 0.1`.
- Without env vars → defaults `4` and `0.05`.

**Import + fixture pattern** (use pytest `monkeypatch` for env isolation):
```python
import pytest
from src.config import get_mcts_config

def test_cognitivo_defaults(monkeypatch):
    monkeypatch.delenv('MCTS_COGNITIVO_PRIOR_COUNT', raising=False)
    monkeypatch.delenv('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', raising=False)
    cfg = get_mcts_config()
    assert cfg['cognitivo_prior_count'] == 4
    assert cfg['cognitivo_prior_mean_delta'] == 0.05
```

---

### `tests/test_optimizer_integration.py` (NEW) — test (integration), request-response

**Analog:** `tests/test_optimizer.py` lines 5–33 (full `Optimizer(...)` construction with `mock_heavy_evaluators`, mocked `selection`/`_expand_node`, `_run_mcts_iteration` invocation).

**Integration smoke-test pattern** (`test_optimizer.py` lines 5–24):
```python
def test_optimizer_layer1_hard_pruning(mock_heavy_evaluators):
    opt = Optimizer(skill_original="foo")
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="foo")
    root.last_reward = 0.0
    child = MCTSNode(instruction=text, parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, is_error, reward = opt._run_mcts_iteration(root)
```

**Tests to write** (no real LLM — mock `agent`/`agent_cognitivo`):
- `Optimizer(skill_original="Test")` → assert `'mutador_cognitivo' in opt.mutation_bandit._counts` and `> 0`; assert `hasattr(opt, 'agent_cognitivo')`.
- Patch `mutation_bandit.select` → `'mutador_cognitivo'`; mock `agent_cognitivo` returning a `MagicMock(nova_instrucao="...", critica="...", raciocinio_estruturado="...")`; run one `_run_mcts_iteration`; assert child `mutation_strategy == 'mutador_cognitivo'`.
- Patch `select` → non-cognitivo key; assert `opt.agent` called and `agent_cognitivo` NOT called.

**Regression guard:** existing `test_optimizer_layer1_hard_pruning` + `test_optimizer_layer2_penalty_multiplier` in `tests/test_optimizer.py` must still pass — extend that file with a `test_optimizer_cognitivo_routing` if colocated regression coverage is preferred.

---

### `tests/test_optimizer.py` (EXTEND) — test, request-response

**Analog:** self — existing tests at lines 5–54. Follow the identical fixture (`mock_heavy_evaluators`) + `MagicMock` setup. Add a routing/regression test appended to the file.

---

## Shared Patterns

### DSPy Signature Declaration
**Source:** `src/signatures.py` lines 15–30 (`StrategyDiscoverer`, `SelfReflectiveAgent`)
**Apply to:** `MutadorCognitivoAgent`
```python
class SelfReflectiveAgent(dspy.Signature):
    """Docstring with OBRIGATÓRIO imperative instructions..."""
    instrucao_anterior: str = dspy.InputField()
    # ...
    nova_instrucao: str = dspy.OutputField(desc="...")
```
Convention: class docstring carries the imperative behavioral instructions; every field has a Portuguese `desc=` for OutputFields, bare type for simple InputFields.

### Pydantic Validator (standalone BaseModel + @field_validator)
**Source:** `src/signatures.py` lines 5–13 (`GeracaoSkill`), 32–56 (`Avaliacao`)
**Apply to:** `RaciocinioCognitivo` + `MutadorCognitivoOutput` (nova_instrucao section validator)
```python
class GeracaoSkill(BaseModel):
    nova_instrucao: str = Field(description="...")
    @field_validator('nova_instrucao')
    def validar_tamanho_instrucao(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("...")
        return v
```
Convention: validators raise `ValueError` with Portuguese message; multi-field validators stack `@field_validator(..., mode='before')` + `@classmethod`.

### Strategy Key Convention
**Source:** `optimizer.py` line 252, `registry.py` line 53
**Apply to:** the `'mutador_cognitivo'` key referenced in registry, bandit priors, and optimizer routing
```python
key_raw = nova_estrat.nome_estrategia.lower()
key = re.sub(r'[^a-z0-9_]', '_', key_raw)[:30] + '_' + str(uuid.uuid4())[:4]
```
Use literal snake_case `'mutador_cognitivo'` (no UUID suffix for the hardcoded seed).

### Config Knob Convention
**Source:** `src/config.py` lines 68–99
**Apply to:** `cognitivo_prior_count`, `cognitivo_prior_mean_delta`
```python
'key_name': type(os.environ.get('MCTS_KEY_NAME', 'default')),
```
Convention: `MCTS_` env-var prefix, string default, explicit `int()`/`float()` cast, inline `# comment` above each knob.

### Test Fixture / Mock Pattern
**Source:** `tests/conftest.py` lines 26–34, `tests/test_optimizer.py` lines 5–7
**Apply to:** all new test files that touch `Optimizer` or DSPy modules
```python
@pytest.fixture
def mock_heavy_evaluators():
    with patch('src.ausculta_modo_b.AvaliadorModoB', autospec=True) as mock_avaliador, \
         patch('sentence_transformers.SentenceTransformer', autospec=True) as mock_st:
        yield {'AvaliadorModoB': mock_avaliador, 'SentenceTransformer': mock_st}

def test_x(mock_heavy_evaluators):
    opt = Optimizer(skill_original="foo")
```
Convention: tests take `mock_heavy_evaluators` as first param to prevent network calls; plain `def test_...()` functions (no classes); direct `assert` statements.

## No Analog Found

None. All 10 files have an exact or role-match analog in the codebase. The new DSPy Signature + Pydantic validator classes are co-located with their direct siblings in `src/signatures.py`.

## Metadata

**Analog search scope:** `src/` (signatures.py, config.py, mutation_strategies/{registry,bandit,api}.py, mutations.py, optimizer.py), `tests/` (conftest.py, test_optimizer.py, test_heuristic_evaluator.py, test_semantic_evaluator.py)
**Files scanned:** 11
**Pattern extraction date:** 2026-07-10

---
*Phase: 06-mutador-cognitivo*
*Pattern map: 2026-07-10*
