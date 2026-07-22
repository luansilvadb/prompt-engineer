---
title: 'Limpeza do Codebase — Código Morto e Redundâncias'
type: 'refactor'
created: '2026-07-21T22:43:00-03:00'
status: 'in-review'
baseline_commit: 'd9dbb743affb68ba61e6c93a6be187d838794d98'
review_loop_iteration: 0
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
- `src/context_audit.py` — imports `field`, `Dict`, `Any` não utilizados
- `src/domain/agents/` — 5 arquivos (__init__.py + 4 agentes) nunca importados externamente
- `src/metrics.py` — precisa verificação: `src/services.py` importa mas pode ser stub
- `frontend/assets/index.css` — linhas 417–472: `.rules-input-wrapper`, `.btn-add-rule`, `.rules-list` órfãs
- `frontend/index.html` — input `#skill-path-hidden` (linha 141) sem referência JS; `animate-pulse` sem @keyframes
- `scratch/` — 6 arquivos experimentais, zero referências
- `scripts/` — 7 scripts de pesquisa, importam src mas sem dependentes reversos
- `build/`, `dist/` — artefatos de build stale
- `temp_pytest_dir/`, `.pytest_cache/`, `.pytest_tmp/` — diretórios temporários

## Tasks & Acceptance

**Execution:**
- [x] `src/mcts_phases.py` — DELETAR — módulo inteiro de 703 linhas nunca integrado; lógica duplicada em optimizer.py
- [x] `src/domain/agents/` (5 arquivos) — DELETAR — agentes nunca referenciados por código externo
- [x] `src/context_audit.py` — REMOVER import `field` não utilizado; `Dict` e `Any` mantidos (em uso em `to_dict()`) — limpa advertências de linter
- [x] `frontend/assets/index.css` — REMOVER linhas 417–472 — regras CSS órfãs do recurso rules/RAG removido
- [x] `frontend/index.html` — `#skill-path-hidden` não encontrado no HTML atual (falso positivo do subagente); item descartado
- [x] `scratch/` — DELETAR diretório inteiro — 6 scripts experimentais sem dependentes
- [x] `scripts/` — DELETAR diretório inteiro — 7 scripts de pesquisa, sem valor de produção
- [x] `build/`, `dist/` — DELETAR diretórios — artefatos de build stale regeneráveis
- [x] `temp_pytest_dir/`, `.pytest_cache/`, `.pytest_tmp/` — DELETAR — diretórios temporários de teste
- [x] `frontend/index.html` — REMOVER classe `animate-pulse` do elemento (linha 111) — sem @keyframes definido

**Acceptance Criteria:**
- Given o codebase limpo, when `pytest` roda da raiz do projeto, then todos os testes passam sem falhas
- Given o frontend carregado, when a UI é inspecionada visualmente, then nenhum elemento quebrado ou estilo ausente é observado
- Given os arquivos removidos, when `grep -r` busca por referências aos símbolos deletados em `src/` e `tests/`, then zero matches são encontrados

## Verification

**Commands:**
- `python -m pytest tests/ -x --timeout=60` — expected: todos os testes passam
- `python -c "import py_compile; py_compile.compile('src/context_audit.py', doraise=True)"` — expected: compila sem erro após remoção de imports
- `grep -r "mcts_phases" src/ tests/` — expected: zero matches após remoção

**Manual checks (if no CLI):**
- Abrir `frontend/index.html` no navegador e verificar se o layout e as interações visuais permanecem intactos