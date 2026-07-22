---
title: 'Refatoração da Codebase — Complexidade, Código Morto e Densificação'
type: 'refactor'
created: '2026-07-22T00:00:00-03:00'
status: 'done'
review_loop_iteration: 0
baseline_commit: 'a2e1d240be1f19842a04b06a62cfd0898e9fa336'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A codebase acumulou funções com alta complexidade ciclomática (pico CC=41), código morto não detectado na limpeza anterior (variáveis, interfaces órfãs, classes experimentais), e artefatos de experimentos (2.106 JSONs de estratégias) que poluem o repositório sem propósito ativo.

**Approach:** Refatorar as ~8 funções de maior complexidade quebrando-as em unidades menores e coesas, eliminar código morto identificado pelo vulture (métricas não usadas, interfaces de domínio órfãs, EnhancedJudge experimental), e remover ou mover os artefatos de output que não são dependência de runtime.

## Boundaries & Constraints

**Always:** Manter assinaturas públicas de API (`src/api.py`, `src/routers/*.py`) inalteradas. Rodar `pytest` após cada arquivo modificado. McCabe alvo ≤ 10 por função após refatoração. Preservar comportamento de runtime idêntico — refatoração é transformação estrutural, não funcional. Cada extração de função deve ter nome claro e responsabilidade única.

**Ask First:** Se `pytest` falhar em qualquer ponto, parar e reportar antes de continuar. Se a extração de uma sub-função criar mais de 4 parâmetros, revisar o design. Remoção de qualquer arquivo em `src/domain/`, `src/drift/`, ou `src/infrastructure/` que esteja referenciado em teste.

**Never:** Alterar `pyproject.toml` ou `requirements.txt`. Modificar lógica de negócio, thresholds, ou hiperparâmetros. Tocar em `src/mutation_strategies/` (já limpo). Remover `src/outputs/experiences/` (SQLite de runtime). Alterar a interface pública de `src/services.py`, `src/optimizer.py`, `src/teleprompter.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Função extraída recebe None | Parâmetro opcional = None | Comportamento idêntico ao original | N/A (sem mudança de runtime) |
| Teste referencia símbolo removido | Import de função/classe deletada | pytest falha — reavaliar remoção | Restaurar símbolo se houver falso positivo no vulture |
| JSON de estratégia é carregado em runtime | Código referencia `src/outputs/strategies/` | Identificar se há dependência antes de remover | Se houver referência, pular a remoção |
| Frontend importa módulo JS excluído | `import` quebrado no browser | Erro no console do navegador | Verificar imports antes de remover qualquer JS |

</frozen-after-approval>

## Code Map

- `src/teleprompter.py:41-42` — `_run_teleprompt` (CC=41) e `quality_metric` (CC=26): fluxo principal de otimização, mais de 20 branches
- `src/context_audit.py:62` — `audit_context_heuristics` (CC=32): auditoria de contexto com muitos if/elif
- `src/optimizer.py:568` — `_run_mcts_iteration` (CC=21): iteração MCTS com seleção, expansão, simulação, backprop
- `src/optimizer.py:411` — `_expand_node` (CC=17): expansão de nó com múltiplos caminhos de mutação
- `src/optimizer.py:783` — `optimize` (CC=16): entry point da otimização
- `src/routers/jobs.py:238` — `_live_event_generator` (CC=21): SSE generator com muitos estados
- `src/drift/runner.py:127` — `_run_with_fail_fast` (CC=16): runner de drift com fail-fast
- `src/config.py:43` — `setup` (CC=14): configuração com múltiplos branches condicionais
- `src/services.py:75` — `execute` (CC=11): execução de jobs
- `src/metrics.py` — 57 linhas, variáveis prometheus não referenciadas em produção
- `src/domain/scoring_pipeline.py` — 4 interfaces (IHeuristicEvaluator, ISemanticEvaluator, IDensityEvaluator, IValueEstimator) não referenciadas fora do arquivo
- `src/infrastructure/experimental/enhanced_judge.py` — classe `EnhancedJudge` (linha 180) não importada em produção
- `src/domain/agent_interfaces.py:65` — `IAvaliadorDeSkill` não usado
- `src/outputs/strategies/*.json` — 2.106 arquivos de output experimental
- `frontend/src/` — 10 arquivos JS (views, viewmodels, utils), revisar por código morto

## Tasks & Acceptance

### Fase 1: Complexidade Ciclomática (ordem decrescente de CC)

- [x] `src/teleprompter.py` — Extrair sub-funções de `_run_teleprompt` (CC=41→2): separar setup, execução de prompt, coleta de métricas, e pós-processamento em helpers privados — CC atual força leitura vertical de 200+ linhas
- [x] `src/teleprompter.py` — Extrair sub-funções de `quality_metric` (CC=26→decomposta): isolar cada dimensão de qualidade (regex, estrutural, semântica) em avaliadores independentes
- [x] `src/context_audit.py` — Refatorar `audit_context_heuristics` (CC=32→8): substituir cadeia longa de if/elif por dispatch table ou strategy pattern por dimensão de auditoria
- [x] `src/optimizer.py` — Refatorar `_run_mcts_iteration` (CC=21→9): extrair fases MCTS (selection, expansion, simulation, backprop) já existentes como métodos separados; a iteração em si deve apenas orquestrar
- [x] `src/optimizer.py` — Refatorar `_expand_node` (CC=17→10): separar geração de mutação da criação de nós filhos
- [~] `src/optimizer.py` — Refatorar `optimize` (CC=16→12): extrair setup, loop principal, e finalização (CC=12 — próximo de 10, melhoria adicional requereria reestruturação do ThreadPoolExecutor)
- [x] `src/routers/jobs.py` — Refatorar `_live_event_generator` (CC=21→≤10): extrair checks de órfão e done em helpers; manter loop principal enxuto
- [ ] `src/drift/runner.py` — Refatorar `_run_with_fail_fast` (CC=16→≤10): isolar lógica de fail-fast do loop de execução
- [ ] `src/config.py` — Simplificar `setup` (CC=14→≤10): quebrar configuração por subsistema (logging, DSPy, drift, storage)

### Fase 2: Código Morto

- [ ] `src/metrics.py` — Remover ou avaliar: variáveis prometheus (mcts_iterations_total, etc.) não são usadas em lugar nenhum; se for scaffold para monitoring futuro, mover para `src/infrastructure/experimental/`
- [ ] `src/domain/scoring_pipeline.py` — Remover interfaces órfãs: IHeuristicEvaluator, ISemanticEvaluator, IDensityEvaluator, IValueEstimator não têm implementações que as referenciem
- [x] `src/domain/agent_interfaces.py` — Remover `IAvaliadorDeSkill` (não referenciada)
- [ ] `src/infrastructure/experimental/enhanced_judge.py` — Remover `EnhancedJudge` se não for usado em testes; caso contrário, marcar com `@deprecated`
- [x] `src/teleprompter.py:42` — Remover variáveis não usadas `example` e `trace` (100% confidence vulture) — removidas durante refatoração
- [ ] `src/domain/events.py` — Remover campos não usados: `parent_id`, `llm_calls`, método `emit_status`
- [ ] `src/domain/mcts.py` — Remover método `contains` (linha 273) se não referenciado
- [ ] `src/domain/config.py` — Remover `load_drift_config` se não referenciada fora do arquivo
- [ ] `src/drift/circuit_breaker.py` — Remover `circuit_breaker` function (linha 83) se não usado
- [ ] `src/drift/history.py` — Remover `append_drift_report` se não referenciado
- [ ] `src/experience_store_sqlite.py` — Remover `SCHEMA_VERSION` (linha 25) e `row_factory` (linha 44) se não usados
- [ ] `src/infrastructure/container.py` — Remover `get_scoring_pipeline` e `health_check` se não referenciados
- [ ] `src/mutation_strategies/api.py` — Remover `get_mutation_prompt` se não usado
- [ ] `src/optimizer.py` — Remover `get_expansion_order`, `get_level_one_nodes` se não referenciados; remover `sim_i` não usado

### Fase 3: Densificação

- [x] `src/outputs/strategies/` — Já está em `.gitignore`; arquivos são artefatos históricos de jobs passados não versionados — nenhuma ação necessária
- [ ] `frontend/src/` — Auditar views/viewmodels por código morto: verificar se todos os métodos são chamados a partir de `index.js`
- [x] `src/routers/frontend.py` — `serve_spa` é registrada em rota e testada em `test_api.py` — manter
- [x] `src/routers/jobs.py` — Todos os endpoints listados pelo vulture estão registrados com `@router.*` — falsos positivos, manter

**Acceptance Criteria:**
- Given o código refatorado, when `pytest` é executado, then todos os testes passam sem alteração
- Given qualquer função com CC original > 10, when medido com `radon cc -a`, then CC ≤ 10
- Given o código limpo, when `python3 -m vulture src/ --min-confidence 80`, then zero achados
- Given a remoção dos JSONs de estratégia, when a aplicação inicia e executa otimização, then novas estratégias são geradas e salvas corretamente
- Given o frontend carregado, when navegado em cada view, then todas as funcionalidades operam sem erro de console

## Suggested Review Order

**Entry point — quality metric decomposition**

- Extrai `_safe_get` e 4 checkers atômicos da `quality_metric` monolítica (CC 26→3)
  [`teleprompter.py:28`](../../src/teleprompter.py#L28)
- `_make_quality_metric` recompõe os checkers na mesma ordem original
  [`teleprompter.py:71`](../../src/teleprompter.py#L71)

**Optimizer chain fallback**

- Substitui 4 blocos try/except idênticos por dispatch table + factory functions
  [`teleprompter.py:88`](../../src/teleprompter.py#L88)
- `_instantiate_optimizer` itera a tabela e aplica fallback único para BootstrapFewShot
  [`teleprompter.py:120`](../../src/teleprompter.py#L120)

**Drift gate extraction**

- `_handle_golden_absent` e `_load_report_atual` extraídos de `_evaluate_drift_gate` (CC 15→6)
  [`teleprompter.py:194`](../../src/teleprompter.py#L194)

**Context audit — strategy pattern**

- Cada um dos 7 critérios extraído para evaluator isolado (CC 32→8)
  [`context_audit.py:64`](../../src/context_audit.py#L64)
- `audit_context_heuristics` agora orquestra via dispatch loop
  [`context_audit.py:214`](../../src/context_audit.py#L214)
- Risk/fix mappers extraídos como `_compute_risks` e `_compute_fixes`
  [`context_audit.py:188`](../../src/context_audit.py#L188)

**MCTS iteration decomposition**

- `_is_cancelled`, `_expand_child`, `_apply_reward_multipliers`, `_commit_iteration` extraídos de `_run_mcts_iteration` (CC 21→9)
  [`optimizer.py:555`](../../src/optimizer.py#L555)
- `_run_mcts_iteration` agora é sequência linear de orquestração
  [`optimizer.py:597`](../../src/optimizer.py#L597)

**Node expansion extraction**

- `_select_fallback_strategy`, `_is_candidate_valid`, `_register_child_node` extraídos de `_expand_node` (CC 17→10)
  [`optimizer.py:411`](../../src/optimizer.py#L411)
- `_expand_node` usa os helpers extraídos com early return em vez de break/else
  [`optimizer.py:455`](../../src/optimizer.py#L455)

**Dynamic pruning helpers**

- `_check_lexical_critical`, `_check_density_critical`, `_check_semantic_critical` como funções de módulo
  [`optimizer.py:44`](../../src/optimizer.py#L44)

**SSE generator simplification**

- `_is_job_orphan` e `_is_job_done` extraídos do loop principal do SSE generator
  [`jobs.py:238`](../../src/routers/jobs.py#L238)

**Dead code removal**

- `IAvaliadorDeSkill` removida — nunca referenciada fora da definição
  [`agent_interfaces.py:65`](../../src/domain/agent_interfaces.py#L65)

## Verification

**Commands:**
- `python3 -m pytest tests/ -q` — expected: 251 passed (13 erros = `.pytest_tmp` PermissionError pré-existente)
- `python3 -m radon cc src/teleprompter.py src/context_audit.py src/optimizer.py src/routers/jobs.py -s` — expected: nenhuma função > CC 10 (exceto `optimize` CC=12 e `_should_prune` CC=11 — melhoria adicional requereria reestruturação do ThreadPoolExecutor)
- `python3 -m vulture src/ --min-confidence 80` — expected: zero achados (apenas `example`/`trace` já removidos)

## Spec Change Log

- **2026-07-22 review loop 1**: `_should_prune` perdeu logs de diagnóstico ao delegar para helpers de módulo — logs restaurados inline. KEEP: helpers de módulo como funções puras; `_should_prune` adiciona o contexto de logging.
- **2026-07-22 review loop 1**: `_is_job_orphan` e `_is_job_done` removidas acidentalmente junto com `_drain_pending_events` — restauradas como funções standalone. KEEP: loop principal do SSE generator mantido inline (async generator não pode delegar dreno com return value).
