---
title: 'Vacuum & Densify — Limpeza Profunda e Reorganização do Projeto'
type: 'refactor'
created: '2026-07-22T01:30:00-03:00'
status: 'done'
baseline_commit: 'a2e1d240be1f19842a04b06a62cfd0898e9fa336'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O projeto acumulou gordura estrutural: shims de 1 linha, artefatos Windows acidentais, diretórios temporários de pytest, especificação de build solta na raiz, 4 módulos avaliadores espalhados em `src/`, dual-backend de experience store com acoplamento confuso, e código experimental marcado como "não integrado em produção" ocupando espaço no source tree.

**Approach:** Remover lixo (nul, .pytest_tmp), eliminar o shim `bandit_interfaces.py`, mover `desktop.py` e `SkillOptimizer.spec` para `scripts/`, consolidar os 4 avaliadores em `src/evaluators/`, deletar `src/infrastructure/experimental/`, e resolver o dual-backend do experience store extraindo tipos compartilhados e migrando `teleprompter.py` para o backend SQLite.

## Boundaries & Constraints

**Always:** Rodar `pytest` após cada lote de alterações. Atualizar todos os imports via grep cross-reference — zero `ModuleNotFoundError`. Preservar comportamento de runtime — nenhuma lógica de negócio alterada. Mudanças puramente estruturais (mover, renomear, deletar, re-exportar).

**Ask First:** Se `pytest` falhar em qualquer etapa, HALT e reportar antes de continuar. Se a migração do `teleprompter.py` para o store SQLite causar divergência de comportamento, HALT e apresentar opções.

**Never:** Alterar lógica de avaliação, otimização MCTS, ou scoring pipeline. Modificar `pyproject.toml` ou `requirements.txt`. Tocar em `src/domain/` (interfaces já estão limpas). Alterar `src/drift/` (já bem organizado).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Deleção de arquivo lixo | `nul`, `.pytest_tmp/` existem no disco | Arquivos/diretórios deletados, git status limpo | Se git tracked, `git rm` antes |
| Eliminação de shim | `bandit_interfaces.py` com 2 consumidores | Arquivo deletado, imports em container.py e services.py apontam para src.domain | Se grep encontrar outros consumidores, atualizar também |
| Movimentação de desktop.py | `desktop.py` na raiz → `scripts/desktop.py` | Arquivo movido, zero referências quebradas (não é importado por ninguém) | Se houver referência externa (ex: build_desktop.ps1), atualizar |
| Consolidação de avaliadores | 4 arquivos → `src/evaluators/` | Todos os imports em optimizer.py, scoring_pipeline.py, container.py atualizados | Se import quebrar, pytest detecta |
| Migração ExperienceStore | teleprompter.py usa JSON store | teleprompter.py passa a usar SQLite store; classe JSON ExperienceStore removida | Se store.create_experience_store() exigir parâmetros diferentes, adaptar |

</frozen-after-approval>

## Code Map

**Lixo e artefatos:**
- `./nul` — artefato Windows de redirecionamento acidental (já no .gitignore, 102 bytes)
- `./.pytest_tmp/` — diretório com ~15 arquivos temporários de pytest, não rastreado
- `./SkillOptimizer.spec` — spec do PyInstaller na raiz (9 linhas)

**Shim a eliminar:**
- `src/mutation_strategies/bandit_interfaces.py` — 1-liner re-export shim; consumidores: `infrastructure/container.py:35`, `src/services.py:12`

**Avaliadores a consolidar:**
- `src/heuristic_evaluator.py` (71 linhas) — `evaluate_heuristics()`, buzzword filter
- `src/density_evaluator.py` (153 linhas) — `compute_lexical_density()`, `calculate_density_multiplier()`, dataclasses
- `src/semantic_evaluator.py` (57 linhas) — `calculate_semantic_penalty()`, `get_embedder()`
- `src/value_estimator.py` (146 linhas) — `ValueEstimator` class

**Código experimental:**
- `src/infrastructure/experimental/__init__.py` — marcador de diretório
- `src/infrastructure/experimental/enhanced_judge.py` (285 linhas) — EnhancedJudge não integrado

**Dual backend experience store:**
- `src/experience_store.py` (247 linhas) — classe `ExperienceStore` (JSON), tipos `Experience`, helpers TF-IDF
- `src/experience_store_sqlite.py` (273 linhas) — `create_experience_store()` (SQLite), importa tipos/helpers do módulo JSON
- `src/teleprompter.py:4,240` — único consumidor direto da classe `ExperienceStore` (JSON)

**Entry points na raiz:**
- `./desktop.py` (194 linhas) — app PyWebView standalone; não referenciado por outros módulos; referenciado por `build_desktop.ps1`

## Tasks & Acceptance

**Execution:**
- [x] `./nul` — DELETAR — artefato Windows, 102 bytes, já no .gitignore
- [x] `.gitignore` — ADICIONAR `.pytest_tmp/` — prevenir recriação acidental
- [x] `./.pytest_tmp/` — DELETAR diretório inteiro — ~15 artefatos temporários de pytest
- [x] `src/mutation_strategies/bandit_interfaces.py` — DELETAR — shim de 1 linha, substituir 2 consumidores por import direto de `src.domain.bandit_interfaces`
- [x] `src/infrastructure/container.py:35` — EDITAR import — `from src.mutation_strategies.bandit_interfaces` → `from src.domain.bandit_interfaces`
- [x] `src/services.py:12` — EDITAR import — `from src.mutation_strategies.bandit_interfaces` → `from src.domain.bandit_interfaces`
- [x] `./SkillOptimizer.spec` — MOVER → `scripts/SkillOptimizer.spec` — spec de build solto na raiz
- [x] `./desktop.py` — MOVER → `scripts/desktop.py` — entry point standalone na raiz
- [x] `scripts/build_desktop.ps1` — EDITAR (se houver referência a `desktop.py`) — atualizar path
- [x] `src/evaluators/__init__.py` — CRIAR — re-exports públicos
- [x] `src/evaluators/heuristic.py` — CRIAR via move de `src/heuristic_evaluator.py` — sem alterações internas
- [x] `src/evaluators/density.py` — CRIAR via move de `src/density_evaluator.py` — sem alterações internas
- [x] `src/evaluators/semantic.py` — CRIAR via move de `src/semantic_evaluator.py` — sem alterações internas
- [x] `src/evaluators/value.py` — CRIAR via move de `src/value_estimator.py` — sem alterações internas
- [x] `src/heuristic_evaluator.py` — DELETAR — movido para `src/evaluators/heuristic.py`
- [x] `src/density_evaluator.py` — DELETAR — movido para `src/evaluators/density.py`
- [x] `src/semantic_evaluator.py` — DELETAR — movido para `src/evaluators/semantic.py`
- [x] `src/value_estimator.py` — DELETAR — movido para `src/evaluators/value.py`
- [x] `src/optimizer.py:35-39` — EDITAR imports — apontar para `src.evaluators.*`
- [x] `src/infrastructure/scoring_pipeline.py:4-5` — EDITAR imports — apontar para `src.evaluators.*`
- [x] `src/infrastructure/container.py:198` — EDITAR import — apontar para `src.evaluators.semantic`
- [x] `src/infrastructure/experimental/` — DELETAR diretório — código não integrado em produção
- [x] `src/experience_store.py` — REMOVER classe `ExperienceStore` (JSON) — manter apenas tipos (`Experience`, `hash_instruction`) e helpers TF-IDF
- [x] `src/experience_store_sqlite.py` — REMOVER fallback para `ExperienceStore` — `create_experience_store()` é única factory
- [x] `src/teleprompter.py` — EDITAR — substituir `ExperienceStore()` por `create_experience_store()`

**Acceptance Criteria:**
- Given o codebase reorganizado, when `python -m pytest tests/ -x -q` roda da raiz, then todos os testes passam sem falhas
- Given os imports atualizados, when `python -c "from src.evaluators import ValueEstimator, evaluate_heuristics, compute_lexical_density, calculate_density_multiplier, calculate_semantic_penalty"` é executado, then todos os imports funcionam sem `ModuleNotFoundError`
- Given o shim eliminado, when `grep -r "bandit_interfaces" src/` é executado, then zero matches (exceto em `src/domain/`)
- Given o código experimental deletado, when `grep -r "infrastructure.experimental" src/` é executado, then zero matches
- Given o dual-backend resolvido, when `grep -r "from src.experience_store import ExperienceStore" src/` é executado, then zero matches (só o SQLite é usado)

## Verification

**Commands:**
- `python -m pytest tests/ -x -q` — expected: todos os testes passam
- `python -c "from src.optimizer import Optimizer"` — expected: import funciona, zero ModuleNotFoundError
- `python -c "from src.services import optimize_skill"` — expected: import funciona
- `python -c "from src.evaluators import ValueEstimator, evaluate_heuristics, compute_lexical_density, calculate_density_multiplier, calculate_semantic_penalty"` — expected: re-exports funcionam
- `grep -rn "bandit_interfaces" src/ --include="*.py" | grep -v "src/domain/"` — expected: zero matches
- `grep -rn "experimental" src/ --include="*.py"` — expected: zero matches
- `ls src/heuristic_evaluator.py src/density_evaluator.py src/semantic_evaluator.py src/value_estimator.py 2>&1` — expected: No such file or directory (todos)

**Manual checks (if no CLI):**
- Inspecionar `src/evaluators/__init__.py` — confirmar que todos os símbolos públicos estão re-exportados
- Inspecionar `src/experience_store.py` — confirmar que classe `ExperienceStore` foi removida mas tipos/helpers permanecem

## Suggested Review Order

**Entry point — consolidação dos avaliadores**

- Novo package `evaluators/` com re-exports de todos os símbolos públicos dos 4 módulos consolidados
  [`__init__.py:1`](../../src/evaluators/__init__.py#L1)

- Arquivo mais pesado entre os consolidados — 153 linhas, densidade lexical e multiplier
  [`density.py:1`](../../src/evaluators/density.py#L1)

- Módulo de heurísticas movido sem alterações — buzzword filter e pruning via textstat
  [`heuristic.py:1`](../../src/evaluators/heuristic.py#L1)

- Avaliador semântico com cache LRU de embeddings — movido sem alterações
  [`semantic.py:1`](../../src/evaluators/semantic.py#L1)

- Value Estimator com TD-learning — movido sem alterações
  [`value.py:1`](../../src/evaluators/value.py#L1)

**Principal consumidor — optimizer.py**

- Consolidou 4 imports de avaliadores em 1 bloco — mesma semântica, menos ruído
  [`optimizer.py:35`](../../src/optimizer.py#L35)

**Experience store — remoção do backend JSON legado**

- Classe `ExperienceStore` (JSON Lines) removida — mantidos apenas tipos `Experience` e helpers TF-IDF
  [`experience_store.py:1`](../../src/experience_store.py#L1)

- Factory simplificada — sem fallback para JSON, só SQLite
  [`experience_store_sqlite.py:253`](../../src/experience_store_sqlite.py#L253)

- `teleprompter.py` migrado para `create_experience_store()` — type hint agora usa Protocol `IExperienceStore`
  [`teleprompter.py:4`](../../src/teleprompter.py#L4)

**Shim e imports — bandit_interfaces**

- Import corrigido: `src.mutation_strategies.bandit_interfaces` → `src.domain.bandit_interfaces`
  [`container.py:35`](../../src/infrastructure/container.py#L35)

- Mesmo ajuste no services.py
  [`services.py:12`](../../src/services.py#L12)

**Scoring pipeline**

- Imports de density e semantic consolidados via `src.evaluators`
  [`scoring_pipeline.py:4`](../../src/infrastructure/scoring_pipeline.py#L4)

**Arquivos movidos para scripts/**

- `desktop.py` movido da raiz — PyWebView entry point sem alterações
  [`desktop.py:1`](../../scripts/desktop.py#L1)

- Spec do PyInstaller movida e atualizada — `Analysis(['scripts/desktop.py'])`
  [`SkillOptimizer.spec:1`](../../scripts/SkillOptimizer.spec#L1)

- Script de build atualizado para apontar para `scripts/SkillOptimizer.spec`
  [`build_desktop.ps1:1`](../../build_desktop.ps1#L1)

**Limpeza**

- `.pytest_tmp/` adicionado ao `.gitignore`
  [`.gitignore:97`](../../.gitignore#L97)

- `src/infrastructure/experimental/` deletado — 285 linhas não integradas

- `nul` deletado — artefato Windows

**Testes**

- 5 arquivos de teste com imports atualizados para `src.evaluators.*`
  [`test_density_evaluator.py:1`](../../tests/test_density_evaluator.py#L1)
  [`test_heuristic_evaluator.py:1`](../../tests/test_heuristic_evaluator.py#L1)
  [`test_semantic_evaluator.py:3`](../../tests/test_semantic_evaluator.py#L3)
  [`test_value_estimator.py:3`](../../tests/test_value_estimator.py#L3)
  [`test_optimizer.py:4`](../../tests/test_optimizer.py#L4)
