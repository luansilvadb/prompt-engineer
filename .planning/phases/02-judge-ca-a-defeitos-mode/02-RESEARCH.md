<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Criar uma **classe separada `AvaliadorModoB(dspy.Signature)`** em `signatures.py`, isolando completamente o novo comportamento sem alterar o `AvaliadorDeSkill` (Modo A). As duas classes coexistem; o Modo A fica disponível apenas como fallback/debug.
- **D-02:** O `AvaliadorModoB` inclui um **novo `OutputField` `defeitos_encontrados`** (lista de strings enumerando violações, paradoxos e ambiguidades detectadas), posicionado antes de `feedback_detalhado` e das notas para forçar estruturalmente o raciocínio do LLM na ordem correta.
- **D-03:** **Por padrão, toda avaliação usa o Modo B.** O Modo A fica disponível apenas como fallback/debug — não é exposto na API de jobs.
- **D-04:** O `DriftRunner` expõe um **método separado `run_modo_b()`** para invocar o `AvaliadorModoB`. Explícito, testável em isolamento, sem afetar o caminho principal do Modo A.
- **D-05:** O `AvaliadorModoB` deve detectar **tudo**: violações de regras explícitas (passadas em `regras_adicionais` e no corpo da skill) + paradoxos internos (instruções mutuamente exclusivas) + ambiguidades perigosas (padrões que tornam o comportamento do agente imprevisível). O campo `defeitos_encontrados` enumera cada item encontrado.
- **D-06:** Criar um **novo modelo Pydantic `AvaliacaoModoB(Avaliacao)`** que herda `Avaliacao` e adiciona `defeitos_encontrados: list[str]`. Isso isola a mudança sem quebrar o contrato atual de `Avaliacao` usado pelo Modo A e pelo `DriftGate` existente.
- **D-07:** Criar um **arquivo separado `ausculta_modo_b.py`** com um novo Golden Set dedicado ao Modo B. O arquivo `ausculta.py` original (Modo A) é preservado para regressões de debug. O novo Golden Set inclui probes com violações explícitas, paradoxos e ambiguidades — cenários que o Modo A não testava. As expectativas de nota nos probes do Modo B refletem o regime de notas mais baixas (ex: ~0.665 para skills disfuncionais).
- **D-08:** Os thresholds de `DriftThresholds` (spearman_floor, offset_alarm) **não são alterados** — a recalibração acontece nas expectativas dos probes, não nos limites do gate.
- **D-09:** Renomear o arquivo atual `outputs/models/avaliador_otimizado.json` para **`avaliador_modo_a_otimizado.json`**. Preparar o path `avaliador_modo_b_otimizado.json` para uso futuro. A função `load_avaliador()` em `signatures.py` recebe um parâmetro `modo` ('a' ou 'b') e seleciona o path correto.
- **D-10:** O `AvaliadorModoB` **começa fresh** (sem Few-Shot carregado). O arquivo `.json` do Modo A não tem utilidade para o Modo B — exemplos de caça-defeitos precisariam ser coletados separadamente (fora do escopo desta fase).
- **D-11:** **A API de jobs (`routers/jobs.py`) não expõe o conceito de modo de avaliação.** O modo é um detalhe interno do pipeline. O default Modo B é aplicado silenciosamente sem parâmetros externos.

### the agent's Discretion
- **Skill "Espelho Distorcido"**: O success criterion do ROADMAP menciona que a verificação local deve comprovar que o Modo B reprova esta skill. O Golden Set do Modo B deve incluir um probe baseado nela (skill com instrução autocontraditória, nota esperada baixa).
- **Exemplo de calibração de nota**: PROJECT.md documenta que o Modo B corrigiu a nota de 0.96 → 0.665 para a skill do "Espelho Distorcido". Os probes de `ausculta_modo_b.py` devem ter `expected_composite ≈ 0.665` para skills disfuncionais e `expected_composite ≈ 0.85+` para skills bem construídas.
- **`defeitos_encontrados` como lista**: Cada item deve ser uma string curta e descritiva, ex: `["Regra 'seja conciso' contradiz 'explique cada passo'", "Campo X nunca definido mas referenciado em Y"]`.

### Deferred Ideas (OUT OF SCOPE)
- **Otimização Few-Shot do `AvaliadorModoB`**: Coletar exemplos rotulados de defeitos e treinar Few-Shot via DSPy BootstrapFewShot. Requer Golden Set do Modo B funcionando primeiro — próxima fase natural.
- **Exposição do modo via API**: Se no futuro houver necessidade de A/B testing externo, adicionar parâmetro `modo_avaliacao` ao endpoint de jobs. Por ora, decisão é manter como detalhe interno.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| JUD-01 | Atualizar o `AvaliadorDeSkill` para priorizar a detecção de contradições comportamentais (Modo B). | Criação de `AvaliadorModoB` e `AvaliacaoModoB` com campo `defeitos_encontrados` em `src/signatures.py`. O pipeline integrará através de `JudgeProbeRunner.run_modo_b()`. |
| JUD-02 | O sistema do `drift_monitor` absorve o novo comportamento do avaliador sem desativar a pipeline ou rejeitar todos os prompts válidos. | Criação de um script `ausculta_modo_b.py` e separação dos arquivos de modelo otimizado e carregamento via `load_avaliador(modo='b')`. Tolerâncias de Gate permanecem as mesmas. |
</phase_requirements>

# Phase 02: Judge "Caça-Defeitos" Mode - Research

**Researched:** 2026-07-09
**Domain:** LLM Evaluation, Testing, and MCTS
**Confidence:** HIGH

## Summary

This research focuses on updating the optimization pipeline to use the Mode B ("Caça-Defeitos") judge. This mode prioritizes detecting behavioral contradictions, internal paradoxes, and dangerous ambiguities before assessing cosmetic text features.

**Primary recommendation:** Introduce `AvaliadorModoB` and `AvaliacaoModoB` as parallel constructs in `src/signatures.py`. Implement `run_modo_b` in the evaluation pipeline without disrupting Mode A pathways, and build a tailored `ausculta_modo_b.py` Golden Set focusing on flawed skills.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| AvaliadorModoB (DSPy Signature) | API / Backend | — | Defines the LLM prompt for evaluating skills in Mode B. Modifies AI evaluation logic without affecting data transport. |
| AvaliacaoModoB (Pydantic Model) | API / Backend | — | Enforces the structure of the Mode B response, adding the `defeitos_encontrados` field. |
| DriftRunner (run_modo_b) | API / Backend | — | Executes the drift testing pipeline using the selected Mode B judge. |
| ausculta_modo_b.py | Testing / QA | — | Sets up the specific Golden Set cases targeted at detecting structural contradictions. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dspy-ai | (existing) | LLM prompting framework | Used natively in `src/signatures.py`. Provides the Signature abstraction to define LLM evaluation prompts. |
| pydantic | (existing) | Validation schemas | `AvaliacaoModoB` extends `Avaliacao` inherited from `pydantic.BaseModel`. |

## Architecture Patterns

### Recommended Project Structure
```
src/
├── signatures.py                  # AvaliadorModoB and AvaliacaoModoB definitions. load_avaliador() handles modo='a'/'b'.
├── drift/
│   └── runner.py                  # JudgeProbeRunner receives run_modo_b()
├── ausculta_modo_b.py             # Script to generate/maintain Golden Set (Mode B)
└── outputs/
    └── models/
        ├── avaliador_modo_a_otimizado.json
        └── avaliador_modo_b_otimizado.json  # Pre-emptively mapped path
```

### Pattern 1: Extending Base Signature
**What:** Creating a side-by-side signature and schema for Mode B to decouple changes and preserve Mode A functionality.
**When to use:** When you need a parallel evaluation methodology without breaking existing workflows.
**Example:**
```python
class AvaliacaoModoB(Avaliacao):
    defeitos_encontrados: list[str] = Field(
        description="Lista de strings enumerando violações, paradoxos e ambiguidades detectadas."
    )
    # The inherited fields keep the exact same logic.
```

### Anti-Patterns to Avoid
- **Overwriting `AvaliadorDeSkill` Directly:** Do not overwrite the existing `AvaliadorDeSkill`. Always create `AvaliadorModoB` side-by-side to preserve the Mode A configuration for potential rollbacks or debugging.
- **Forcing Pydantic Validations into the Gate directly:** The `DriftGate` relies on `DriftReport`, meaning `AvaliacaoModoB` must seamlessly parse back down to the required metrics in `run_modo_b` and `drift/metrics.py`.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `outputs/golden/golden_set.json` (may be affected if overwriting) | Script `ausculta_modo_b.py` should target a different golden set file or distinctly label Mode B probes. |
| Live service config | None — verified by repo structure. | none |
| OS-registered state | None — verified by repo structure. | none |
| Secrets/env vars | None — verified by repo structure. | none |
| Build artifacts | `outputs/models/avaliador_otimizado.json` | Rename to `avaliador_modo_a_otimizado.json`. |

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | custom (drift_monitor.py / golden set) |
| Config file | none — see Wave 0 |
| Quick run command | `python src/drift_monitor.py` |
| Full suite command | `python src/drift_monitor.py` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| JUD-01 | AvaliadorModoB class detects defects | integration | `python src/drift_monitor.py` | ❌ Wave 0 (needs ausculta_modo_b.py) |
| JUD-02 | Pipeline uses Mode B smoothly | smoke | `python src/drift_monitor.py` | ✅ Wave 0 (drift_monitor.py existing) |

### Wave 0 Gaps
- [ ] `src/ausculta_modo_b.py` — Required to test JUD-01 (Golden Set Mode B, specifically Espelho Distorcido).

## Sources

### Primary (HIGH confidence)
- Codebase check in `src/signatures.py`, `src/drift/runner.py`, `src/drift/gate.py`, and `src/drift/models.py`.
- `ausculta.py` and `drift/golden.py` reviewed to establish exact implementation plan for the new Mode B golden set.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Core logic is native to the project (DSPy/Pydantic).
- Architecture: HIGH - Follows strict constraints laid out by the user in `02-CONTEXT.md`.
- Pitfalls: HIGH - Clearly derived from system integration points observed via `view_file`.

**Research date:** 2026-07-09
**Valid until:** 30 days
