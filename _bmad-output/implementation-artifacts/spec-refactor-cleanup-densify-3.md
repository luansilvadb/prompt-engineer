---
title: 'Refatoração da Codebase - Rodada 3: Código Morto e Densificação'
type: 'refactor'
created: '2026-07-22'
status: 'done'
baseline_commit: 'f70249f2c6a4bacae7e55cd337be42ad885c201c'
review_loop_iteration: 0
context: []
---

<frozen-after-approval>

## Intent

**Problem:** A codebase acumulou código morto não detectado em rodadas anteriores — métricas Prometheus nunca incrementadas (7 contadores, 57 linhas), método `audit_skill` órfão, wrapper `_calculate_score` de uma linha — e duplicações que elevam custo de manutenção: 3 listas independentes de buzzwords com entradas divergentes, computação de TTR duplicada entre `density.py` e `heuristic.py`, e dependência circular config↔signatures via `_sanitize_unicode_for_api`.

**Approach:** Eliminar todo código sem propósito ativo (princípio: "está sendo usado e faz algo necessário agora?"), consolidar duplicações em fonte única de verdade, e quebrar a dependência circular extraindo o sanitizer para módulo utilitário.

## Boundaries & Constraints

**Always:** Preservar comportamento externo de toda API REST, CLI e SSE. Manter cobertura de testes existente executando `pytest` após cada bloco. Rodar `ruff check` com zero violações novas. Usar tipagem e padrões do código ao redor.

**Ask First:** Alterações em lógica de negócio. Mudanças em assinaturas de API pública.

**Never:** Refatorar `src/optimizer.py` (escopo próprio). Alterar endpoints REST. Modificar lógica de LLM/DSPy além de mover imports. Adicionar funcionalidades. Modificar frontend. Reduzir complexidade ciclomática em funções de runtime (deferido para rodada própria — ver deferred-work.md).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Endpoint `/metrics` após remoção | `GET /metrics` | 404 ou removido das rotas | N/A |
| Auditoria de skill | `POST /api/audit` com texto | Resultado idêntico — continua usando `audit_context_heuristics()` direto | Erros de parsing mantidos |
| Avaliação heurística com texto em pt-BR | Chamada a `avaliar_heuristicas()` | Buzzwords detectados com `src/evaluators/buzzwords.py` (mesmo conjunto após consolidação) | Fallback se módulo ausente |
| Compilação DSPy | `POST /api/compile` | Comportamento inalterado; sanitizer carregado de `src/utils/unicode_sanitizer.py` | Erros de encoding tratados como antes |
| Serviço de otimização | `OptimizationService.start_optimization()` | Funcionamento inalterado após remoção de `audit_skill` | N/A |

</frozen-after-approval>

## Code Map

- `src/metrics.py` — 7 contadores Prometheus (57 linhas) nunca incrementados — remover
- `src/api.py:13,60-62` — import e rota `/metrics` — remover após metrics.py
- `src/services.py:142-148` — `audit_skill()` nunca chamado — remover
- `src/signatures.py:288-289` — `_calculate_score` wrapper de 1 linha — inline e remover
- `scripts/compile_dspy.py:1` — `import sys` não usado — remover
- `src/context_audit.py:51-58` — `_VAGUE_BUZZWORDS` (18 padrões) — consolidar
- `src/evaluators/heuristic.py:10-23,54-56` — `_VAGUE_BUZZWORDS` (23 padrões, diferente) + TTR inline — consolidar
- `src/drift/metrics.py:115-123` — `_STYLE_BUZZWORDS` (23 padrões) — consolidar
- `src/evaluators/density.py:6-8` — `compute_lexical_density()` — referência para TTR
- `src/signatures.py:12-47` — `_UNICODE_REPLACEMENTS` e `_sanitize_unicode_for_api` — extrair
- `src/config.py:8,49-75` — import de signatures.py para sanitizer — atualizar

## Tasks & Acceptance

**Execution:**
- [x] `src/metrics.py` — REMOVER arquivo inteiro — 7 contadores nunca incrementados
- [x] `src/api.py` — REMOVER `import` de metrics e rota `/metrics` — endpoint retornava dados vazios
- [x] `src/services.py` — REMOVER método `audit_skill` (linhas 142-148) — nunca chamado
- [x] `src/signatures.py` — REMOVER `_calculate_score` e inline chamada única em `funcao_de_recompensa` — wrapper sem valor
- [x] `scripts/compile_dspy.py` — REMOVER `import sys` não utilizado
- [x] Criar `src/evaluators/buzzwords.py` — CONSOLIDAR `BUZZWORDS` como união das 3 listas existentes (sem duplicatas) — fonte única
- [x] `src/context_audit.py` — SUBSTITUIR `_VAGUE_BUZZWORDS` local por `from src.evaluators.buzzwords import VAGUE_BUZZWORD_RE`
- [x] `src/evaluators/heuristic.py` — SUBSTITUIR `_VAGUE_BUZZWORDS` local por import de buzzwords.py; SUBSTITUIR TTR inline por `compute_lexical_density()` de density.py
- [x] `src/drift/metrics.py` — SUBSTITUIR `_STYLE_BUZZWORDS` local por `from src.evaluators.buzzwords import STYLE_BUZZWORDS_LOWER`
- [x] Criar `src/utils/unicode_sanitizer.py` — MOVER `_UNICODE_REPLACEMENTS` e `_sanitize_unicode_for_api` de signatures.py — quebra dependência circular
- [x] `src/signatures.py` — SUBSTITUIR definições movidas por import de `src.utils.unicode_sanitizer`; manter re-export para compatibilidade
- [x] `src/config.py` — ATUALIZAR import de `_sanitize_unicode_for_api` para `src.utils.unicode_sanitizer`

**Acceptance Criteria:**
- Given a codebase pós-refatoração, when `pytest tests/ -x -q` é executado, then todos os testes existentes passam
- Given a codebase pós-refatoração, when `ruff check src/ scripts/ main.py` é executado, then zero violações novas
- Given a codebase pós-refatoração, when `grep -r "from.*metrics\|import.*metrics" src/ --include="*.py"` é executado, then zero ocorrências
- Given a codebase pós-refatoração, when `grep -r "_VAGUE_BUZZWORDS\|_STYLE_BUZZWORDS" src/ --include="*.py"` é executado, then apenas imports do módulo consolidado (fora buzzwords.py)
- Given a codebase pós-refatoração, when `grep -r "_UNICODE_REPLACEMENTS\|_sanitize_unicode_for_api" src/signatures.py` é executado, then apenas imports/re-exports

## Spec Change Log

- **Review loop 1** (2026-07-22): Blind Hunter identificou docstring stale em `calcular_composite` referenciando `_calculate_score` removido — corrigido. Edge Case Hunter identificou lazy import de `compute_lexical_density` dentro de `evaluate_heuristics` — movido para top-level. Ambos reviewers notaram que a consolidação de buzzwords expande silenciosamente o conjunto de padrões no context_audit (18→30) — analisado como working-as-designed (spec explicitamente descreve união das 3 listas). 4 defers registrados para rodadas futuras.

## Design Notes

**Consolidação de buzzwords:** União das 3 listas via `set.union` produz ~30 padrões únicos. Documentar origem de cada entrada com comentário inline para rastreabilidade. A lista consolidada em `buzzwords.py` é a única fonte; nenhum outro módulo define buzzwords localmente.

**Unicode sanitizer — quebra de dependência circular:** `config.py` importa `_sanitize_unicode_for_api` de `signatures.py`, e `signatures.py` transita por `config.py` via `infrastructure/`. Mover para `src/utils/` elimina o acoplamento. Manter re-export em `signatures.py` para compatibilidade com imports existentes.

**Remoção de metrics.py:** Arquivo e referências removidos completamente. Se observabilidade for necessária no futuro, instrumentar no local de uso, não como definições órfãs.

## Verification

**Commands:**
- `pytest tests/ -x -q` -- expected: all tests pass
- `ruff check src/ scripts/ main.py` -- expected: zero new violations
- `python main.py check skills/bom.md` -- expected: CLI funcional (runtime smoke test)

## Suggested Review Order

**Dead code removal**

- Entrada principal: remoção do endpoint `/metrics` e imports associados, mais remoção do `import Response` não utilizado
  [`api.py:10`](../../src/api.py#L10)

- Remoção do método `audit_skill` órfão — nunca chamado, endpoint usa `audit_context_heuristics()` direto
  [`services.py:142`](../../src/services.py#L142)

- Remoção do wrapper `_calculate_score` de uma linha; chamada única inline para `calcular_composite`
  [`signatures.py:288`](../../src/signatures.py#L288)

- Remoção de `import sys` não utilizado no script de compilação
  [`compile_dspy.py:1`](../../scripts/compile_dspy.py#L1)

**Buzzwords consolidation**

- Novo módulo consolidado: união das 3 listas independentes (context_audit, heuristic, drift) em fonte única
  [`buzzwords.py:1`](../../src/evaluators/buzzwords.py#L1)

- context_audit substitui lista local de 18 padrões por import do módulo consolidado
  [`context_audit.py:50`](../../src/context_audit.py#L50)

- heuristic substitui lista local de 28 padrões + TTR inline por imports de buzzwords.py e density.py
  [`heuristic.py:3`](../../src/evaluators/heuristic.py#L3)

- drift/metrics substitui lista local de 23 strings por import do módulo consolidado
  [`metrics.py:5`](../../src/drift/metrics.py#L5)

**Unicode sanitizer extraction**

- Novo módulo utilitário: quebra dependência circular config ↔ signatures
  [`unicode_sanitizer.py:1`](../../src/utils/unicode_sanitizer.py#L1)

- signatures.py remove ~52 linhas de definições, importa do novo módulo com re-export
  [`signatures.py:4`](../../src/signatures.py#L4)

- config.py atualiza import do sanitizer para o novo caminho
  [`config.py:49`](../../src/config.py#L49)

- dspy_impl.py atualiza import do sanitizer para o novo caminho
  [`dspy_impl.py:3`](../../src/infrastructure/dspy_impl.py#L3)
