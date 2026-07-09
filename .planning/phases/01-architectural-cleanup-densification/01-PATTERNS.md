# Phase 1: Architectural Cleanup & Densification - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 11 new/modified files (2 source files split into 8 new units + 2 shim/modified sources + ~4 dead-code touch-ups)
**Analogs found:** 11 / 11

> No RESEARCH.md exists for this phase. File list extracted from `01-CONTEXT.md`
> decisions, `REQUIREMENTS.md` (ARC-01/02/03), and the codebase intel docs.
> `CONCERNS.md` explicitly flags: *"drift_monitor.py contains classes for domain
> exceptions, metric calculations, and file IO"* — this is the densification target.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/drift/exceptions.py` *(new)* | utility | — (pure) | `src/drift_monitor.py` L44-50 (current home of `DriftMeasurementError`) | exact (extract) |
| `src/drift/models.py` *(new)* | model | — (data) | `src/drift_monitor.py` L57-148 (dataclass block) + `src/signatures.py` (model grouping) | exact (extract) |
| `src/drift/golden.py` *(new)* | service | file-I/O | `src/drift_monitor.py` L155-248 (`GoldenSet`) + `src/store.py` (atomic persistence) | exact (extract) |
| `src/drift/runner.py` *(new)* | service | request-response (LLM) | `src/drift_monitor.py` L314-359 (`JudgeProbeRunner`) | exact (extract) |
| `src/drift/metrics.py` *(new)* | utility | transform (pure) | `src/drift_monitor.py` L366-469 (`_spearman_rank_correlation`, `medir_drift`) | exact (extract) |
| `src/drift/gate.py` *(new)* | service | decision (transform) | `src/drift_monitor.py` L476-553 (`DriftGate`) | exact (extract) |
| `src/drift/circuit_breaker.py` *(new)* | service | file-I/O | `src/drift_monitor.py` L560-607 (`verificar_juiz_atual`, `circuit_breaker`) | exact (extract) |
| `src/drift/cache.py` *(new)* | service | file-I/O | `src/drift_monitor.py` L614-652 (`load_drift_cache`, `save_drift_cache`) | exact (extract) |
| `src/mutations/registry.py` *(new)* | service | file-I/O | `src/mutations.py` L27-71 (`StrategyRegistry` + `registry`) | exact (extract) |
| `src/mutations/bandit.py` *(new)* | service | transform | `src/mutations.py` L77-125 (`MutationBandit`) | exact (extract) |
| `src/mutations/api.py` *(new)* | utility | — (pure) | `src/mutations.py` L128-132 (`get_mutation_prompt`, `get_strategy_description`) | exact (extract) |
| `src/drift_monitor.py` *(modified → shim)* | facade | import-pass-through | `src/routers/__init__` (implicit) — namespace re-export | role-match |
| `src/mutations.py` *(modified → shim)* | facade | import-pass-through | `src/routers/__init__` (implicit) — namespace re-export | role-match |
| `src/optimizer.py` *(modified — dead code)* | service | transform | self (ARC-01 cleanup pass) | self |
| `src/teleprompter.py` *(modified — dead code)* | service | request-response | self (ARC-01 cleanup pass) | self |
| `src/services.py` *(modified — dead code)* | service | request-response | self (ARC-01 cleanup pass) | self |
| `src/api.py` *(modified — dead code)* | controller | request-response | self (ARC-01 cleanup pass) | self |

**Note on `__init__.py`:** The repo has **zero `__init__.py` files** (verified via glob). The existing `src/routers/` subpackage works as a Python 3 implicit **namespace package**. New `src/drift/` and `src/mutations/` packages MUST follow the same convention — **do not create `__init__.py`**. Compatibility with existing `from src.drift_monitor import X` import paths is preserved by keeping the old module files as thin re-export shims (see Pattern Assignments).

---

## Pattern Assignments

### `src/drift/exceptions.py` (utility, pure)

**Analog (extract source):** `src/drift_monitor.py` lines 44-50

```python
class DriftMeasurementError(Exception):
    """Falha na medição de drift (LLM indisponível, JSON ilegível, etc.)."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
```

**Pattern to follow:** Move verbatim. This is the canonical "domain exception with context dict" pattern referenced in `CONVENTIONS.md` ("Domain-specific exceptions are used"). Single class, single responsibility, no imports beyond stdlib.

---

### `src/drift/models.py` (model, data)

**Analog (extract source):** `src/drift_monitor.py` lines 57-148 — the dataclass block.
**Secondary analog (organization style):** `src/signatures.py` — groups all `BaseModel`/`dspy.Signature` data definitions in one module.

```python
@dataclass(frozen=True)
class ProbeExpectation:
    """Notas esperadas de um probe ..."""
    manteve_regras_criticas: bool
    nota_clareza: float
    # ... 6 dims total
    def composite_score(self) -> float:
        return calcular_composite(self)   # delegates to signatures.calcular_composite

@dataclass(frozen=True)
class GoldenProbe:
    id: str
    skill_original: str
    # ...

@dataclass(frozen=True)
class DimensionError:
    dimension: str
    mae: float

@dataclass
class DriftReport:
    judge_label: str
    spearman_composite: float
    # ... field(default_factory=list) for list fields
    def to_dict(self) -> dict:
        return { ... }

@dataclass(frozen=True)
class GateDecision:
    accept: bool
    reason: str
    triggered_metric: Optional[str] = None

@dataclass(frozen=True)
class DriftThresholds:
    spearman_floor: float = 0.8
    # ...
    @classmethod
    def from_config(cls, cfg: dict) -> 'DriftThresholds':
        return cls(...)
```

**Pattern to follow:** Group ALL frozen/mutable dataclasses here. **Dependency note:** `ProbeExpectation.composite_score` calls `calcular_composite` from `src.signatures` — keep that import:
```python
from src.signatures import calcular_composite
```
**Immutability convention** (from `CONVENTIONS.md`): use `@dataclass(frozen=True)` for value objects (`ProbeExpectation`, `GoldenProbe`, `DimensionError`, `GateDecision`, `DriftThresholds`); use plain `@dataclass` for aggregators with mutable list fields (`DriftReport`). Keep `DriftReport.to_dict()` and `DriftThresholds.from_config()` on their classes — they travel with the data.

---

### `src/drift/golden.py` (service, file-I/O)

**Analog (extract source):** `src/drift_monitor.py` lines 155-248 (`GoldenSet`).
**Secondary analog (atomic write):** `store.py` (uses same temp-file + `os.replace` idiom — see Shared Patterns).

```python
GOLDEN_DIR = Path('src/outputs/golden')

class GoldenSet:
    def __init__(self):
        self.version: str = ''
        self.probes: List[GoldenProbe] = []
        self._load()

    def _store_path(self) -> Path:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        return GOLDEN_DIR / 'golden_set.json'

    def _load(self):
        path = self._store_path()
        if not path.exists():
            import sys
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # frozen-executable fallback (PyInstaller) ...
        # ... json.load → ProbeExpectation(**pd['expected']) → GoldenProbe(...)

    def save(self, version: str, curated_at: str):
        """Persistência atômica — USAR APENAS EM CURADORIA OFFLINE (BR3)."""
        path = self._store_path()
        temp_path = path.with_suffix('.tmp')
        # ... build dict ...
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
```

**Pattern to follow — ARC-02 (reduce complexity) target:** `_load()` (lines 171-207) has 4 nested branches (exists / frozen / re-exists / try). **Extract two helpers:**
- `_restore_frozen_golden(path) -> Path` — the PyInstaller `sys._MEIPASS` block (lines 174-184)
- `_parse_golden_json(data) -> List[GoldenProbe]` — the probe parsing loop (lines 193-203)
so `_load()` becomes a flat sequence of early-returns. **Do not** introduce a Strategy/Factory class — CONTEXT.md explicitly forbids overengineering ("Evitar overengineering com Padrões de Projeto complexos").

**Immutability rule** (`CONVENTIONS.md`): `save()` stays offline-only; runtime is read-only. Preserve the BR3 docstring.

---

### `src/drift/runner.py` (service, request-response / LLM)

**Analog (extract source):** `src/drift_monitor.py` lines 314-359.

```python
import dspy
from src.signatures import AvaliadorDeSkill, Avaliacao, _invoke_judge_with
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import ProbeMeasurement
from src.drift.golden import GoldenProbe

class JudgeProbeRunner:
    def __init__(self, label: str):
        self.label = label
        self._judge = dspy.Predict(AvaliadorDeSkill)

    def load_candidate(self, path: str) -> None:
        try:
            self._judge.load(path)
        except Exception as e:
            raise DriftMeasurementError(
                f"Falha ao carregar juiz candidato de {path}",
                context={'judge_label': self.label, 'path': path, 'original': str(e)},
            )

    def as_zero(self) -> None:
        self._judge = dspy.Predict(AvaliadorDeSkill)

    def run(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        # loop repetitions → _invoke_judge_with(...) → samples.append
        # raise DriftMeasurementError if 0 samples
```

**Pattern to follow:** Isolated DSPy instance pattern (Norma 3 / R2: `.demos` is per-instance — the docstring at L315-319 is load-bearing, **preserve it verbatim**). Keep the `try/except → DriftMeasurementError(context=...)` contract.

---

### `src/drift/metrics.py` (utility, transform / pure)

**Analog (extract source):** `src/drift_monitor.py` lines 366-469 (`_spearman_rank_correlation` + `medir_drift`).

```python
def _spearman_rank_correlation(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 2:
        return 1.0
    def ranks(values):
        order = sorted(range(n), key=lambda i: values[i])
        rank = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                rank[order[k]] = avg_rank
            i = j + 1
        return rank
    rx = ranks(x); ry = ranks(y)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))

def medir_drift(runner, golden, repetitions, thresholds) -> DriftReport:
    if golden.is_empty():
        raise DriftMeasurementError("Golden set vazio — nada a medir.")
    # ... long body: measurements → spearman → offset → mae_per_dim → per_probe
```

**Pattern to follow — ARC-02 (reduce complexity) targets:**
1. `_spearman_rank_correlation` — extract the inner `ranks(values)` closure (lines 376-388) into a **module-level** `_compute_ranks(values: List[float]) -> List[float]`. The nested `while/while` becomes a flat standalone function — drops cyclomatic complexity of the parent significantly.
2. `medir_drift` (lines 400-469) is ~70 lines with 5 distinct sections. Extract:
   - `_measure_all_probes(runner, golden, repetitions) -> List[tuple]`
   - `_compute_mae_per_dimension(measurements, dims) -> List[DimensionError]`
   - `_compute_concordance_and_violations(measurements) -> tuple` (concordance, total_missed, total_false_rej)
   - `_build_per_probe(measurements) -> List[dict]`
   so `medir_drift` is a flat compose-and-return.

**Pure-function convention** (`config.py` is the analog): no class, no state, explicit type hints, returns domain objects. Keep `_` prefix on internal helpers (project convention — see `_invoke_judge`, `_calculate_score`, `_drift_cache_path`).

---

### `src/drift/gate.py` (service, decision / transform)

**Analog (extract source):** `src/drift_monitor.py` lines 476-553 (`DriftGate`).

```python
class DriftGate:
    @staticmethod
    def avaliar_candidato(report_cand, report_atual, thresholds) -> GateDecision:
        if report_cand.critical_rules_violated:
            return GateDecision(False, f"juiz aprovou {report_cand.missed_violations} ...", "critical_rules")
        strict_required = report_cand.low_confidence
        def _strict_better_or_reject(...):  # ← DEAD CODE — defined, never called
            ...
        # Passo 3 — Spearman (if report_atual is not None / else absolute floor)
        # Passo 4 — Offset   (if report_atual is not None / else absolute floor)
        # Passo 2 — low_confidence warning
        return GateDecision(True, "candidato nao regrediu", None)
```

**Pattern to follow — ARC-01 (dead code) + ARC-02 (complexity):**
1. **DELETE the unused `_strict_better_or_reject` nested function** (lines 500-509) — defined but never called (verified via grep: only 1 occurrence in repo). Also remove the now-orphaned `strict_required` assignment at line 498 if it has no remaining reader (it is only referenced inside the deleted helper and the final low-confidence message — verify before removing the line; the message block does not read `strict_required`, only `report_cand.low_confidence`, so the assignment itself is dead).
2. **ARC-02:** the duplicated `if report_atual is not None: <regression-margin check> else: <absolute-floor check>` structure appears twice (Spearman L511-525, Offset L527-541). Extract a tiny helper:
   ```python
   def _gate_against_baseline_or_floor(cand_val, atual_val, threshold_abs, margin,
                                       better_when_lower, metric_name, fmt) -> Optional[GateDecision]:
       ...
   ```
   **Caveat (CONTEXT.md):** keep it a *simple function*, NOT an OO Strategy. The project explicitly bans OO patterns here.

**Decision-rule convention:** hierarchical early-return with `GateDecision(accept, reason, triggered_metric)`. Preserve the comment headers (`# Passo 1/2/3/4`) — they document the gate ordering invariant.

---

### `src/drift/circuit_breaker.py` (service, file-I/O)

**Analog (extract source):** `src/drift_monitor.py` lines 560-607.

```python
def verificar_juiz_atual(thresholds, repetitions) -> Optional[DriftReport]:
    golden = GoldenSet()
    if golden.is_empty():
        return None
    runner = JudgeProbeRunner("atual")
    model_path = MODELS_DIR / 'avaliador_otimizado.json'
    if model_path.exists():
        runner.load_candidate(str(model_path))
    else:
        runner.as_zero()
    return medir_drift(runner, golden, repetitions, thresholds)

def circuit_breaker(thresholds, repetitions) -> GateDecision:
    report = verificar_juiz_atual(thresholds, repetitions)
    if report is None:
        return GateDecision(True, "golden ausente; nada a verificar", None)
    if report.critical_rules_violated:
        # os.replace(model_path, backup) → rollback to zero judge (BR4)
        ...
    return GateDecision(True, f"juiz atual ok ...", None)
```

**Pattern to follow:** module-level functions (not a class). Keep `MODELS_DIR = Path('src/outputs/models')` as module constant. The `circuit_breaker` rename-with-timestamp logic (lines 590-597) stays inline — it is small and already single-purpose. Imports become:
```python
from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.drift.models import DriftReport, GateDecision
```

---

### `src/drift/cache.py` (service, file-I/O)

**Analog (extract source):** `src/drift_monitor.py` lines 614-652.

```python
def _drift_cache_path() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / 'drift_cache.json'

def load_drift_cache() -> Optional[DriftReport]:
    path = _drift_cache_path()
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return DriftReport(...)   # rebuild from dict
    except Exception:
        return None

def save_drift_cache(report: DriftReport) -> None:
    """Persistência atômica do DriftReport do juiz em produção."""
    path = _drift_cache_path()
    temp_path = path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        print(f"[!] Falha ao salvar drift cache ({e}).")
```

**Pattern to follow:** atomic-write idiom (temp + `os.replace`) — see Shared Patterns. Resilient fallback: load failure → return `None`; save failure → log `[!]` and continue. Keep `_` prefix on the path helper (internal).

---

### `src/mutations/registry.py` (service, file-I/O)

**Analog (extract source):** `src/mutations.py` lines 27-71.

```python
STRATEGIES_DIR = Path('src/outputs/strategies')

class StrategyRegistry:
    def __init__(self):
        self.strategies: Dict[str, Dict[str, str]] = {}
        self._load()

    def _store_path(self) -> Path:
        STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
        return STRATEGIES_DIR / 'discovered_strategies.json'

    def _load(self): ...
    def save(self): ...
    def add_strategy(self, key, name, prompt): ...
    def get_prompt(self, key) -> str: ...   # __DISCOVER__ → ''
    def get_name(self, key) -> str: ...     # __DISCOVER__ → display name
    def get_all_keys(self) -> List[str]: ...

# Instância global do registry
registry = StrategyRegistry()
```

**Pattern to follow:** identical shape to `GoldenSet` — `_store_path()` + `_load()`/`save()` + accessors. Keep the module-level singleton `registry = StrategyRegistry()` (consumed by `optimizer.py` L234/249 and `test_discoverer.py` L5 — **this name MUST remain importable**).

**ARC-02 target:** `_load()` (lines 36-43) and `save()` (lines 45-51) swallow exceptions with bare `except Exception: pass`/`self.strategies = {}`. Keep the resilient behavior (CONTEXT decision: no behavior change), but consider logging via the `[!]` print convention for parity with `drift_monitor.py` style — optional, low priority.

---

### `src/mutations/bandit.py` (service, transform)

**Analog (extract source):** `src/mutations.py` lines 77-125.

```python
class MutationBandit:
    def __init__(self, c_param: float = 1.41):
        self.c_param = c_param
        self._counts: Dict[str, int] = {'__DISCOVER__': 0}
        self._rewards: Dict[str, float] = {'__DISCOVER__': 0.0}
        for k in registry.get_all_keys():
            self._ensure_key(k)

    def _ensure_key(self, strategy): ...
    def load_priors(self, strategy_stats): ...
    def select(self) -> str: ...
    def update(self, strategy, reward): ...
```

**Pattern to follow — ARC-02 (reduce complexity) target:** `select()` (lines 104-120) mixes two policies (untried-first vs. UCB1). Extract:
```python
def _pick_untried(self) -> Optional[str]: ...      # lines 110-112
def _ucb_score(self, strategy, total_pulls) -> float: ...  # promote closure (lines 114-118) to method
```
so `select()` reads: ensure keys → try untried → else `max(..., key=lambda s: self._ucb_score(s, total))`.

**Import:** `from src.mutations.registry import registry` (bandit depends on registry singleton — keep construction-time coupling explicit).

---

### `src/mutations/api.py` (utility, pure)

**Analog (extract source):** `src/mutations.py` lines 128-132.

```python
from src.mutations.registry import registry

def get_mutation_prompt(strategy: str) -> str:
    return registry.get_prompt(strategy)

def get_strategy_description(strategy: str) -> str:
    return registry.get_name(strategy)
```

**Pattern to follow:** thin public façade over the registry singleton. Both functions are consumed by `optimizer.py` (L257/258/424/432) — names/signatures MUST not change. This is the analog of `signatures.py`'s `_calculate_score` → `calcular_composite` delegation pattern (thin wrapper over a single source of truth).

---

### `src/drift_monitor.py` *(modified → compatibility shim)*

**Analog:** the implicit re-export behavior of `src/routers/` (consumers do `from src.routers import jobs` then access `jobs.router`). Here the OLD module path becomes a re-export façade so existing imports keep working.

```python
"""
Drift Monitor — façade de compatibilidade (Phase 1 densification).

A implementação foi dividida em módulos pequenos sob src/drift/.
Este arquivo re-exporta o público para preservar os import paths:
    from src.drift_monitor import DriftGate, GoldenSet, medir_drift, ...
(preserva retrocompatibilidade — fora-de-escopo quebrar imports.)
"""
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import (
    ProbeExpectation, GoldenProbe, DimensionError, DriftReport,
    GateDecision, DriftThresholds, ProbeMeasurement,
)
from src.drift.golden import GoldenSet, GOLDEN_DIR
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift, _spearman_rank_correlation
from src.drift.gate import DriftGate
from src.drift.circuit_breaker import verificar_juiz_atual, circuit_breaker
from src.drift.cache import load_drift_cache, save_drift_cache, _drift_cache_path

__all__ = [
    'DriftMeasurementError', 'ProbeExpectation', 'GoldenProbe', 'DimensionError',
    'DriftReport', 'GateDecision', 'DriftThresholds', 'ProbeMeasurement',
    'GoldenSet', 'GOLDEN_DIR', 'JudgeProbeRunner', 'medir_drift',
    '_spearman_rank_correlation', 'DriftGate', 'verificar_juiz_atual',
    'circuit_breaker', 'load_drift_cache', 'save_drift_cache', '_drift_cache_path',
]
```

**Required public surface** (verified via grep — DO NOT drop any of these):
| Symbol | Consumer |
|--------|----------|
| `DriftGate`, `DriftMeasurementError`, `DriftThresholds`, `GoldenSet`, `JudgeProbeRunner`, `load_drift_cache`, `medir_drift`, `save_drift_cache` | `src/teleprompter.py` L8-17 |
| `DriftThresholds`, `circuit_breaker`, `verificar_juiz_atual` | `src/routers/jobs.py` L204-208 |

`MODELS_DIR` is also used inside the module — keep it exported (re-export from `circuit_breaker.py` or `cache.py`).

---

### `src/mutations.py` *(modified → compatibility shim)*

**Analog:** same façade pattern as `src/drift_monitor.py` above.

```python
"""
Mutation Strategies — façade de compatibilidade (Phase 1 densification).

Implementação dividida em src/mutations/{registry,bandit,api}.py.
Re-exporta o público para preservar:
    from src.mutations import registry, MutationBandit, get_mutation_prompt, ...
"""
from src.mutations.registry import StrategyRegistry, registry
from src.mutations.bandit import MutationBandit
from src.mutations.api import get_mutation_prompt, get_strategy_description

__all__ = [
    'StrategyRegistry', 'registry', 'MutationBandit',
    'get_mutation_prompt', 'get_strategy_description',
]
```

**Required public surface** (verified via grep):
| Symbol | Consumer |
|--------|----------|
| `registry` | `src/optimizer.py` L234/249; `test_discoverer.py` L5 |
| `MutationBandit` | `src/optimizer.py` L29/138 |
| `get_mutation_prompt`, `get_strategy_description` | `src/optimizer.py` L257/258/424/432 |

---

### `src/optimizer.py`, `src/teleprompter.py`, `src/services.py`, `src/api.py` *(modified — ARC-01 dead code pass)*

**Analog:** self — these files are NOT being restructured, only pruned. Use the same `import` block conventions already present:

```python
# optimizer.py L24-30 (existing convention — absolute, src-rooted, grouped)
from src.signatures import SelfReflectiveAgent, StrategyDiscoverer, funcao_de_recompensa, calcular_delta_reward, load_avaliador
from src.config import get_mcts_config
from src.experience_store import ExperienceStore, Experience, hash_instruction
from src.value_estimator import ValueEstimator
from src.mutations import MutationBandit, get_mutation_prompt, get_strategy_description, registry

# teleprompter.py L8-17 (multi-line parenthesized import)
from src.drift_monitor import (
    DriftGate, DriftMeasurementError, DriftThresholds, GoldenSet,
    JudgeProbeRunner, load_drift_cache, medir_drift, save_drift_cache,
)
```

**Pattern to follow (ARC-01):** scan each file for unused imports / unreferenced module-level vars / orphan functions. Tools: `Grep` for each imported symbol within its own file; any symbol with exactly 1 occurrence (the import line) is dead → delete the import. After the `drift_monitor`/`mutations` split, these files' imports **do not change** (the shims preserve the paths) — the dead-code pass is independent. Preserve the `from src.X import (...)` parenthesized style for multi-symbol imports.

---

## Shared Patterns

### 1. Namespace-package layout (no `__init__.py`)
**Source:** `src/routers/` (verified: repo has zero `__init__.py` files).
**Apply to:** `src/drift/`, `src/mutations/` (new packages).
```python
# Consumers import by absolute path; no __init__.py needed (Python 3.3+ namespace pkg)
from src.drift.gate import DriftGate
from src.mutations.bandit import MutationBandit
```
**Rule:** Do NOT create `src/drift/__init__.py` or `src/mutations/__init__.py`. Match the existing `src/routers/` convention exactly.

### 2. Absolute imports rooted at `src`
**Source:** every existing module (e.g. `src/optimizer.py` L24-30, `src/teleprompter.py` L8-17, `src/routers/jobs.py` L8-13).
**Apply to:** ALL new files inside `src/drift/` and `src/mutations/`.
```python
# inside src/drift/gate.py:
from src.drift.models import DriftReport, GateDecision, DriftThresholds
# NOT: from .models import ...   (relative imports not used in this codebase)
```
**Rule:** always `from src.<pkg>.<module> import Symbol`. Multi-symbol imports use parenthesized multi-line form.

### 3. Atomic file persistence (temp + `os.replace`)
**Source:** `src/drift_monitor.py` L218-248 (`GoldenSet.save`) and L643-651 (`save_drift_cache`).
**Apply to:** any new/modified file that writes JSON state (`src/drift/golden.py`, `src/drift/cache.py`, `src/mutations/registry.py`).
```python
path = self._store_path()
temp_path = path.with_suffix('.tmp')
with open(temp_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
os.replace(temp_path, path)   # atomic on same filesystem
```
**Rule:** never write directly to the target path; always temp-then-replace. `ensure_ascii=False, indent=2` is the project's JSON formatting standard.

### 4. Resilient fallback + prefixed console logging
**Source:** `src/drift_monitor.py` L185-206, L596-597, L651-652; `src/mutations.py` L42-43/50-51.
**Apply to:** all file-I/O and LLM-call sites in new files.
```python
if not path.exists():
    print(f"[!] Golden set ausente em {path}. Portão operará em fail-open.")
    return
try:
    ...
except Exception as e:
    print(f"[!] Erro ao carregar golden set ({e}). Operando sem âncora.")
    self.probes = []
```
**Rule:** prefix conventions: `[*]` info / `[!]` warning-error / `[+]` success. Swallow-and-continue for non-fatal I/O; raise `DriftMeasurementError(context={...})` for fatal LLM-measurement failures.

### 5. Frozen-executable (PyInstaller) detection
**Source:** `src/drift_monitor.py` L174-184; `src/routers/frontend.py` L8-11; `src/api.py` L19-22.
**Apply to:** `src/drift/golden.py` (preserved verbatim in the `_load` extraction).
```python
import sys
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    frozen_path = Path(sys._MEIPASS) / 'src' / 'outputs' / 'golden' / 'golden_set.json'
    # fallback to bundled data
```
**Rule:** keep this block when extracting `_load()` — it is load-bearing for the packaged desktop build (`desktop.py`).

### 6. Domain exception with context dict
**Source:** `src/drift_monitor.py` L44-50 (`DriftMeasurementError`), consumed at L330-333 and L355-358.
**Apply to:** `src/drift/exceptions.py`; any new domain error.
```python
raise DriftMeasurementError(
    f"Todas as {repetitions} repetições falharam no probe {probe.id}",
    context={'judge_label': self.label, 'probe_id': probe.id, 'failures': failures},
)
```

### 7. Dataclass immutability convention
**Source:** `src/drift_monitor.py` L57-148.
**Apply to:** `src/drift/models.py`.
- `@dataclass(frozen=True)` for value objects and config (`ProbeExpectation`, `GoldenProbe`, `DimensionError`, `GateDecision`, `DriftThresholds`).
- Plain `@dataclass` for aggregators with `field(default_factory=list)` (`DriftReport`, `ProbeMeasurement`).
- Classmethods for construction-from-config (`DriftThresholds.from_config`) live ON the class.

### 8. Cyclomatic-complexity reduction — helper functions, NOT patterns
**Source:** CONTEXT.md decision *"Usar funções auxiliares simples ... Evitar overengineering com Padrões de Projeto complexos (como OO Strategy)."*
**Apply to:** all ARC-02 work in `gate.py`, `metrics.py`, `golden.py`, `bandit.py`.
```python
# DO: extract small private helpers
def _compute_ranks(values: List[float]) -> List[float]: ...
def _gate_against_baseline_or_floor(...): ...

# DON'T: introduce class hierarchies
class GatePolicy(ABC): ...              # ← banned by CONTEXT.md
class SpearmanPolicy(GatePolicy): ...   # ← banned by CONTEXT.md
```
**Rule:** `_`-prefix for internal helpers (project convention). Keep extracted helpers at module scope (or as `@staticmethod`), not nested closures, to flatten the branch count.

---

## No Analog Found

None. Every new/modified file has an exact in-codebase analog (the file it is being extracted from, plus the `src/routers/` subpackage convention for packaging). The planner can reference real excerpts for every assignment.

---

## Metadata

**Analog search scope:**
- `D:\good\src\` (all 16 `.py` modules)
- `D:\good\src\routers\` (existing subpackage — packaging analog)
- Top-level `D:\good\*.py` (`main.py`, `desktop.py`, `analyze_judge.py`, `test_discoverer.py` — consumer import verification)
- `.planning/codebase/{STRUCTURE,ARCHITECTURE,CONVENTIONS,CONCERNS}.md`

**Files scanned:** 20 source files + 4 intel docs.

**Public-surface verification (grep-confirmed consumers):**
- `mutations.py` public API → consumed by `optimizer.py`, `test_discoverer.py`
- `drift_monitor.py` public API → consumed by `teleprompter.py`, `routers/jobs.py`

**Dead-code findings (ARC-01), concrete:**
- `src/drift_monitor.py` L500-509: `_strict_better_or_reject` nested fn — defined, never called.
- `src/drift_monitor.py` L498: `strict_required = report_cand.low_confidence` — assigned, never read after helper removal.
- Further per-file unused-import/unused-var pruning deferred to execute phase (per-symbol grep in `optimizer.py`, `teleprompter.py`, `services.py`, `api.py`).

**Pattern extraction date:** 2026-07-09
