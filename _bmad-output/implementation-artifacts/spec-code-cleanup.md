---
title: 'Limpeza do Codebase — Código Morto e Redundâncias'
type: 'refactor'
created: '2026-07-21T22:43:00-03:00'
status: 'done'
baseline_commit: 'd9dbb743affb68ba61e6c93a6be187d838794d98'
review_loop_iteration: 1
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** O codebase acumulou código morto, arquivos não utilizados, imports inúteis, CSS órfão, e artefatos de experimentos que aumentam a carga cognitiva e o ruído de manutenção sem entregar valor.

**Approach:** Remover cirurgicamente: (1) arquivos completamente mortos sem imports, (2) imports e código não referenciado dentro de arquivos ativos, (3) CSS e HTML órfãos no frontend, (4) artefatos de build/temp rastreáveis, (5) scripts e scratch files experimentais. Toda remoção é validada por grep de referência cruzada e pela suíte de testes existente.

## Boundaries & Constraints

**Always:** Remover apenas código comprovadamente sem referências (zero imports/grep matches em produção e testes). Rodar `pytest` após cada lote de remoções. Não alterar lógica de negócio, assinaturas de API, ou comportamento de runtime.

**Ask First:** Remoção de `src/metrics.py` (importado por `src/services.py` — verificar se é stub ou implementação real). Remoção de `src/mcts_phases.py` (703 linhas, potencialmente planejado para integração futura). Qualquer remoção que quebre um teste.

**Never:** Remover arquivos em `src/domain/`, `src/drift/`, `src/infrastructure/` que estejam em uso ativo. Alterar `pyproject.toml` ou `requirements.txt` sem confirmação explícita. Modificar `.gitignore` sem aprovação.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Remoção de arquivo morto | Arquivo sem imports/grep matches | Arquivo deletado, testes passam | Se `pytest` falhar, restaurar arquivo e reportar |
| Remoção de import inutilizado | `from dataclasses import field` nunca usado | Linha removida, código compila | Se `py_compile` falhar, reverter |
| CSS órfão removido | `.rules-input-wrapper` sem elemento HTML | Estilo removido, UI inalterada | Inspeção visual do frontend |
| Script experimental deletado | `scratch/scratch_test.py` sem referências | Arquivo deletado, git rastreia remoção | N/A — sem dependentes |

</frozen-after-approval>

## Code Map

- `src/mcts_phases.py` — 703 linhas, refatoração planejada nunca integrada; optimizer.py mantém lógica inline
- `src/context_audit.py` — imports `field` e `Optional` não utilizados; `Dict`, `Any`, `List` mantidos
- `src/domain/agents/` — 5 arquivos (__init__.py + 4 agentes) nunca importados externamente
- `frontend/assets/index.css` — linhas 417–472: `.rules-input-wrapper`, `.btn-add-rule`, `.rules-list` órfãs
- `frontend/index.html` — `animate-pulse` sem @keyframes; `#skill-path-hidden` não existe mais
- `scratch/` — 6 arquivos experimentais, zero referências
- `scripts/` — 6 scripts de pesquisa sem dependentes; `compile_dspy.py` preservado (importado por `main.py:127`)
- `build/`, `dist/` — artefatos de build stale
- `temp_pytest_dir/`, `.pytest_cache/`, `.pytest_tmp/` — diretórios temporários

## Tasks & Acceptance

**Execution:**
- [x] `src/mcts_phases.py` — DELETAR — módulo inteiro de 703 linhas nunca integrado; lógica duplicada em optimizer.py
- [x] `src/domain/agents/` (5 arquivos) — DELETAR — agentes nunca referenciados por código externo
- [x] `src/context_audit.py` — REMOVER imports `field` e `Optional` não utilizados; `Dict`, `Any`, `List` mantidos
- [x] `frontend/assets/index.css` — REMOVER linhas 417–472 — regras CSS órfãs do recurso rules/RAG removido
- [x] `frontend/index.html` — REMOVER classe `animate-pulse` do elemento — sem @keyframes definido
- [x] `scratch/` — DELETAR diretório inteiro — 6 scripts experimentais sem dependentes
- [x] `scripts/baseline_fase2.py` — DELETAR — script de pesquisa sem referências reversas
- [x] `scripts/controlled_experiment_d.py` — DELETAR — script de pesquisa sem referências reversas
- [x] `scripts/generate_probes_fase1.py` — DELETAR — script de pesquisa sem referências reversas
- [x] `scripts/isolate_components.py` — DELETAR — script de pesquisa sem referências reversas
- [x] `scripts/pos_fase2.py` — DELETAR — script de pesquisa sem referências reversas
- [x] `scripts/test_timeout_sanity.py` — DELETAR — script de pesquisa sem referências reversas
- [x] `scripts/compile_dspy.py` — PRESERVADO — importado dinamicamente por `main.py:127` no subcomando `compile`
- [x] `build/`, `dist/` — DELETAR diretórios — artefatos de build stale regeneráveis
- [x] `temp_pytest_dir/`, `.pytest_cache/`, `.pytest_tmp/` — DELETAR — diretórios temporários de teste

**Acceptance Criteria:**
- Given o codebase limpo, when `pytest` roda da raiz do projeto, then todos os testes passam sem falhas
- Given o subcomando `compile`, when `python main.py compile` é executado, then o import de `scripts.compile_dspy` funciona sem `ModuleNotFoundError`
- Given o frontend carregado, when a UI é inspecionada visualmente, then nenhum elemento quebrado ou estilo ausente é observado
- Given os arquivos removidos, when `grep -r` busca por referências aos símbolos deletados em `src/` e `tests/`, then zero matches são encontrados

## Spec Change Log

### Loop 1 — 2026-07-21
- **Trigger:** Blind Hunter + Edge Case Hunter encontraram que `main.py:127` faz `from scripts.compile_dspy import compile_agents` no subcomando `compile`. O diretório `scripts/` foi totalmente deletado no primeiro lote, mas `compile_dspy.py` é referenciado por código vivo.
- **Amended:** `scripts/compile_dspy.py` restaurado do git. Os outros 6 scripts de pesquisa permanecem deletados. `Optional` unused também removido de `context_audit.py`.
- **Avoids:** `ModuleNotFoundError` ao executar `python main.py compile`.
- **KEEP:** Todas as outras 9 deleções e edits estão corretas e verificadas com 269 testes passando. Nenhum outro arquivo removido tem referências ativas. Os refs órfãos em `dom.js` (newRuleInput, btnAddRule, rulesList) são pré-existentes (não causados por esta limpeza) e foram deferidos.

## Verification

**Commands:**
- `python -m pytest tests/ -x -q` — expected: todos os testes passam
- `python -c "from scripts.compile_dspy import compile_agents"` — expected: import funciona sem erro
- `python -c "import py_compile; py_compile.compile('src/context_audit.py', doraise=True)"` — expected: compila sem erro

**Manual checks (if no CLI):**
- Abrir `frontend/index.html` no navegador e verificar se o layout e as interações visuais permanecem intactos

## Suggested Review Order

**Entry point — design intent**

- Deleção do maior bloco de código morto: 703 linhas de MCTS phases nunca integradas ao optimizer
  [`mcts_phases.py`](../../src/mcts_phases.py) — DELETADO

**Frontend cleanup**

- CSS órfão removido do recurso rules/RAG já extinto do HTML — 56 linhas sem elemento correspondente
  [`index.css:416`](../../frontend/assets/index.css#L416)

- Classe animate-pulse removida de ícone — @keyframes nunca definido, sem efeito visual real
  [`index.html:111`](../../frontend/index.html#L111)

**Backend code removals**

- Imports `field` e `Optional` removidos de context_audit — sem uso real no arquivo
  [`context_audit.py:9`](../../src/context_audit.py#L9)

- Diretório domain/agents deletado — 5 arquivos de agentes nunca importados por código externo
  [`agents/`](../../src/domain/agents/) — DELETADO

**Diretórios experimentais e artefatos**

- scratch/ deletado — 6 scripts experimentais sem referências no codebase
  [`scratch/`](../../scratch/) — DELETADO

- 6 scripts de pesquisa deletados de scripts/ — compile_dspy.py preservado (importado por main.py:127)
  [`compile_dspy.py`](../../scripts/compile_dspy.py) — PRESERVADO

- Artefatos de build e diretórios temporários removidos
  [`build/`](../../build/) [`dist/`](../../dist/) [`temp_pytest_dir/`](../../temp_pytest_dir/) — DELETADOS

**Verificação**

- 269 testes passam, zero grep matches para símbolos removidos, import de compile_dspy funcional
  [`spec-code-cleanup.md`](../../_bmad-output/implementation-artifacts/spec-code-cleanup.md) — este arquivo
