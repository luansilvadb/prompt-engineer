# Phase 2: Judge "Caça-Defeitos" Mode - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 3
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/signatures.py` | model | request-response | `src/signatures.py` | exact |
| `src/drift/runner.py` | component | request-response | `src/drift/runner.py` | exact |
| `src/ausculta_modo_b.py` | test | batch | `src/drift/golden.py` | partial |

## Pattern Assignments

### `src/signatures.py` (model, request-response)

**Analog:** `src/signatures.py`

**Imports pattern** (lines 1-3):
```python
import dspy
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
```

**Pydantic Model Extension pattern** (lines 32-41):
```python
class Avaliacao(BaseModel):
    manteve_regras_criticas: bool = Field(description="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    nota_clareza: float = Field(description="Nota de 0 a 100 avaliando se a instrução é clara e direta.")
    # ... outras notas ...
    feedback_detalhado: str = Field(description="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")
```
*(Planner: Create `AvaliacaoModoB` inheriting from `Avaliacao`, adding `defeitos_encontrados: list[str]` before `feedback_detalhado`.)*

**DSPy Signature Extension pattern** (lines 58-75):
```python
class AvaliadorDeSkill(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA é estruturalmente superior à original.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restrições ou métricas extras especificadas pelo usuário que devem ser estritamente seguidas.")
    
    manteve_regras_criticas: str = dspy.OutputField(desc="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    # ... notas ...
    feedback_detalhado: str = dspy.OutputField(desc="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")
```
*(Planner: Create `AvaliadorModoB` mimicking this signature but adding `defeitos_encontrados` as an OutputField.)*

**Model loading pattern** (lines 79-87):
```python
def load_avaliador():
    model_path = Path('src/outputs/models/avaliador_otimizado.json')
    if model_path.exists():
        try:
            avaliador_module.load(str(model_path))
            print(f"[*] Avaliador otimizado (Few-Shot) carregado de {model_path}.")
        except Exception as e:
            print(f"[!] Erro ao carregar avaliador otimizado: {e}")
```
*(Planner: Update to accept `modo='a'|'b'` and map to `avaliador_modo_{a|b}_otimizado.json`.)*

---

### `src/drift/runner.py` (component, request-response)

**Analog:** `src/drift/runner.py`

**Judge Runner Setup pattern** (lines 13-15):
```python
    def __init__(self, label: str):
        self.label = label
        self._judge = dspy.Predict(AvaliadorDeSkill)
```
*(Planner: Need to either adapt this to inject the correct judge class or instantiate `AvaliadorModoB` explicitly for Mode B.)*

**Core execution pattern** (lines 31-45):
```python
    def run(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        measurement = ProbeMeasurement(probe_id=probe.id)
        failures = 0
        for _ in range(repetitions):
            try:
                exemplo = dspy.Example(
                    skill_original=probe.skill_original,
                    regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                )
                predicao = dspy.Prediction(skill_otimizada=probe.skill_otimizada)
                avaliacao = _invoke_judge_with(self._judge, exemplo, predicao)
                measurement.samples.append(avaliacao)
            except Exception:
                failures += 1
```
*(Planner: Create `run_modo_b()` method that follows this try-catch/loop structure but uses `AvaliadorModoB` logic.)*

---

### `src/ausculta_modo_b.py` (test, batch)

**Analog:** `src/drift/golden.py`

**Golden Probe Creation pattern** (lines 42-52):
```python
        for pd in data.get('probes', []):
            exp = ProbeExpectation(**pd['expected'])
            probes.append(GoldenProbe(
                id=pd['id'],
                skill_original=pd['skill_original'],
                skill_otimizada=pd['skill_otimizada'],
                regras_adicionais=pd.get('regras_adicionais', ''),
                expected=exp,
                expected_rank_band=pd['expected_rank_band'],
                verifier=pd.get('verifier', ''),
            ))
```
*(Planner: `ausculta_modo_b.py` should construct new `GoldenProbe` definitions directly testing contradictions/paradoxes, specifically aiming for lower scores like `0.665` on contradictory skills.)*

## Metadata

**Analog search scope:** `src/`
**Files scanned:** 4
**Pattern extraction date:** 2026-07-09
