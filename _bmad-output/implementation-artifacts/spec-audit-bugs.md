---
title: 'Auditoria de Bugs Pós-Refatoração — Regressões e Código Residual'
type: 'bugfix'
created: '2026-07-22T02:45:00-03:00'
status: 'done'
review_loop_iteration: 0
baseline_commit: '79591fab64fd77a5351e643fb3ad241f9867156c'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Duas rodadas de refatoração (complexidade ciclomática + código morto) foram concluídas, mas a inspeção adversarial revelou: (a) 4 funções extraídas de `_run_mcts_iteration` foram revertidas silenciosamente no commit `ffcead7` (CC=19, spec afirmava CC=9); (b) funções auxiliares de poda (`_check_lexical_critical` etc.) foram inlineadas violando instrução KEEP do review loop; (c) race condition no `_run_threaded_search` impede detecção de plateau; (d) `_live_event_generator` ficou acima do target de CC (12 vs ≤10).

**Approach:** Re-extrair as 4 helpers de `_run_mcts_iteration` conforme o design original do commit `8bcac64`, restaurar as funções de poda como funções puras de módulo, corrigir a race condition com leitura atômica de `consecutive_zeros`, e reduzir `_live_event_generator` para CC ≤ 10.

## Boundaries & Constraints

**Always:** Manter assinaturas públicas inalteradas. Rodar `pytest` após cada arquivo modificado. McCabe alvo ≤ 10 por função. Preservar comportamento de runtime idêntico. Cada extração com nome claro e responsabilidade única.

**Ask First:** Se `pytest` falhar. Se extração criar função com mais de 4 parâmetros.

**Never:** Alterar `pyproject.toml` ou `requirements.txt`. Modificar lógica de negócio, thresholds, ou hiperparâmetros. Alterar a API pública de qualquer módulo.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| `_run_mcts_iteration` com leaf sem filhos | `leaf.children` vazio, `max_children_allowed > 0` | Expande nó, simula, backpropaga | Virtual loss limpo em todos os branches |
| `_run_threaded_search` com 5 iterações consecutivas reward=0 | `consecutive_zeros` deve acumular entre threads | Aborta por plateau após 5 zeros consecutivos | Lock protege leitura E escrita de `consecutive_zeros` |
| `_should_prune` com instruction vazia | `instruction=""` | `compute_lexical_density("")` retorna 0, condição `0 < 0 < 0.15` é False, continua | N/A |
| `_live_event_generator` com job cancelado durante dreno | `CancelledError` durante `events_queue.get()` | SSE encerra com evento `end: cancelled` | Capturado por `except CancelledError` |

</frozen-after-approval>

## Code Map

- `src/optimizer.py:557-628` — `_run_mcts_iteration` (CC=19): as 4 helpers extraídas em `8bcac64` foram inlineadas em `ffcead7`
- `src/optimizer.py:214-246` — `_should_prune` (CC=11): funções de poda inlineadas, viola KEEP do review loop
- `src/optimizer.py:792-829` — `_run_threaded_search` (CC=6): race condition em `consecutive_zeros`/`consecutive_api_errors`
- `src/routers/jobs.py:247-296` — `_live_event_generator` (CC=12): acima do target de ≤10
- `src/domain/config.py:10-63` — `MCTSConfig.__post_init__` (CC=12): validação complexa não endereçada
- `src/domain/mcts.py:200-228` — `TranspositionTable._normalize_key` (CC=12): normalização com múltiplos branches
- `src/teleprompter.py:79` — `example`/`trace` parâmetros DSPy: falso positivo conhecido do vulture

## Tasks & Acceptance

**Execution:**
- [x] `src/optimizer.py` — Re-extrair `_is_cancelled`, `_expand_child`, `_apply_reward_multipliers`, `_commit_iteration` de `_run_mcts_iteration` (CC=19→9) — as funções existiam em `8bcac64` e foram revertidas; restaurar o design original
- [x] `src/optimizer.py` — Re-extrair `_check_lexical_critical`, `_check_density_critical`, `_check_semantic_critical` como funções puras de módulo de `_should_prune` — viola KEEP explícito do spec change log da rodada 1
- [x] `src/optimizer.py` — Corrigir race condition: proteger leitura de `consecutive_zeros`/`consecutive_api_errors` com `self.lock` em `run_task` antes de passar para `_run_single_iteration`
- [x] `src/routers/jobs.py` — Extrair lógica de dreno e consumo de eventos de `_live_event_generator` para helpers `_drain_pending_events` e `_try_consume_event` (CC=12→10)
- [x] `src/domain/config.py` — Extrair validações individuais de `MCTSConfig.__post_init__` para helpers `_validate_bounds`, `_validate_thresholds`, `_validate_density`, `_validate_root_samples`, `_validate_selection_policy` (CC=12→1)
- [x] `src/domain/mcts.py` — Extrair stages de normalização de `_normalize_key` para `_strip_markdown_fences` e `_collapse_blank_lines` (CC=12→3)

**Acceptance Criteria:**
- Given o código corrigido, when `pytest` é executado, then todos os 269 testes passam sem alteração
- Given `_run_mcts_iteration`, when medido com `radon cc -a`, then CC ≤ 10
- Given `_should_prune`, when medido com `radon cc -a`, then CC ≤ 10
- Given `_live_event_generator`, when medido com `radon cc -a`, then CC ≤ 10
- Given `MCTSConfig.__post_init__`, when medido com `radon cc -a`, then CC ≤ 10
- Given `_normalize_key`, when medido com `radon cc -a`, then CC ≤ 10
- Given o código limpo, when `python3 -m vulture src/ --min-confidence 80`, then zero achados (exceto `example`/`trace` — falso positivo DSPy)
- Given `_run_threaded_search`, when 5+ iterações consecutivas retornam reward=0, then plateau abort dispara corretamente

## Suggested Review Order

**Entry point — extração dos 4 helpers do MCTS iteration (regressão corrigida)**

- Restaura `_is_cancelled`, `_expand_child`, `_apply_reward_multipliers`, `_commit_iteration` que foram inlineados no commit `ffcead7`
  [`optimizer.py:574`](../../src/optimizer.py#L574)
- `_run_mcts_iteration` agora delega para os 4 helpers — CC reduzido de 19 para 9
  [`optimizer.py:619`](../../src/optimizer.py#L619)

**Funções de poda restauradas como módulo**

- `_check_lexical_critical`, `_check_density_critical`, `_check_semantic_critical` extraídas como funções puras (KEEP do review loop)
  [`optimizer.py:47`](../../src/optimizer.py#L47)
- `_should_prune` delegando para os helpers com log prefix restaurado
  [`optimizer.py:237`](../../src/optimizer.py#L237)

**Race condition — leitura atômica no ThreadPoolExecutor**

- `consecutive_zeros` agora lido dentro do lock antes de passar para `_run_single_iteration`
  [`optimizer.py:826`](../../src/optimizer.py#L826)

**SSE generator — extração de dreno e consumo de eventos**

- `_drain_pending_events` e `_try_consume_event` extraídos de `_live_event_generator` (CC 12→10)
  [`jobs.py:247`](../../src/routers/jobs.py#L247)
- `_live_event_generator` agora orquestra com helpers delegados
  [`jobs.py:274`](../../src/routers/jobs.py#L274)

**Validação de config — 5 validadores atômicos**

- `_validate_selection_policy`, `_validate_bounds`, `_validate_thresholds`, `_validate_density`, `_validate_root_samples` extraídos
  [`config.py:48`](../../src/domain/config.py#L48)
- `__post_init__` reduzido a 5 chamadas (CC 12→1)
  [`config.py:40`](../../src/domain/config.py#L40)

**Normalização de chaves — strip de fences e collapse de blank lines**

- `_strip_markdown_fences` e `_collapse_blank_lines` extraídos de `_normalize_key` (CC 12→3)
  [`mcts.py:274`](../../src/domain/mcts.py#L274)
- `_normalize_key` simplificado delegando para os helpers; `import re` movido para module-level
  [`mcts.py:201`](../../src/domain/mcts.py#L201)

## Spec Change Log

- **2026-07-22 review loop 1 (patch):** Log prefix restaurado para `[Poda Dinâmica de Ações]` (removido acidentalmente na re-extração). Docstring de `_try_consume_event` corrigida.

## Design Notes

**Race condition em `_run_threaded_search`:** todas as tasks são submetidas de uma vez a um `ThreadPoolExecutor`. Cada `run_task` lê `consecutive_zeros` do closure antes de adquirir o lock — como todas começam juntas, leem 0. O lock só protege a escrita de volta. Correção: mover a leitura para dentro do `with self.lock` ou passar o valor como argumento após leitura atômica.

**Restauração dos helpers de `_run_mcts_iteration`:** o commit `8bcac64` extraiu corretamente 4 helpers com CC baixo. O commit `ffcead7` (3 minutos depois, mesma mensagem) os inlineou de volta. O código em `8bcac64` serve como referência direta para a re-extração. As funções eram:
- `_is_cancelled(self) -> bool`: encapsula `self._emitter.is_cancelled() or getattr(self, '_abort_flag', False)`
- `_expand_child(self, leaf) -> MCTSNode`: expansão com virtual loss gerenciado
- `_apply_reward_multipliers(self, reward, heuristic_result, child) -> float`: aplica heurística, semântica, densidade
- `_commit_iteration(self, child, reward, feedback) -> None`: atualiza best_reward, bandit, experience store

**Funções de poda como módulo:** a instrução KEEP do review loop da rodada 1 dizia explicitamente "helpers de módulo como funções puras". O commit `ffcead7` as inlineou. Restaurar como:
- `_check_lexical_critical(instruction: str) -> bool`
- `_check_density_critical(instruction: str, ref_instruction: str, mutation_strategy: str = "") -> bool`
- `_check_semantic_critical(instruction: str, parent_instruction: str) -> bool`

## Verification

**Commands:**
- `python3 -m pytest tests/ -q` — expected: 269 passed
- `python3 -m radon cc src/optimizer.py src/routers/jobs.py src/domain/config.py src/domain/mcts.py -s` — expected: nenhuma função > CC 10
- `python3 -m vulture src/ --min-confidence 80` — expected: apenas `example` e `trace` (falso positivo DSPy)
