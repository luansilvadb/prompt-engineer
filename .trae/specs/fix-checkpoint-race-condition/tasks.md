# Tasks

- [x] Task 1: Armazenar scores dos gates no MCTSNode para uso no fallback
  - [x] SubTask 1.1: Adicionar campos `gate_ab_score: float = 0.0` e `gate_post_eval_score: float = 0.0` no `MCTSNode` em `src/domain/mcts.py`
  - [x] SubTask 1.2: No fluxo de estratégia composta (`_expand_node`, linha ~960), após `_create_child_node`, definir `child.gate_ab_score = score_mut` e `child.gate_post_eval_score = post_score_mut` ANTES do `return child`
  - [x] SubTask 1.3: No fluxo de estratégia isolada (`_expand_node`, linha ~1023), após `_create_child_node`, definir `child.gate_ab_score = score_mut` e `child.gate_post_eval_score = post_score_mut` ANTES do `return child`
  - [x] SubTask 1.4: Garantir que `gate_ab_score` e `gate_post_eval_score` são preservados durante `merge_stats` (transposition merge) — se o nó mergeado já tem scores de gate, manter o maior

- [x] Task 2: Adicionar parâmetro configurável `min_time_for_gates_s` no `MCTSConfig`
  - [x] SubTask 2.1: Adicionar campo `min_time_for_gates_s: float = 10.0` em `MCTSConfig` (`src/domain/config.py`), com validação `[1.0, 60.0]`
  - [x] SubTask 2.2: Adicionar leitura via `MCTS_MIN_TIME_FOR_GATES_S` no `from_env()`
  - [x] SubTask 2.3: Adicionar função `_validate_min_time_for_gates_s` seguindo o padrão das validações existentes

- [x] Task 3: Time-gate preventivo + checkpoint provisório + fallback em `_run_mcts_iteration`
  - [x] SubTask 3.1: Antes de chamar `_expand_child` (linha ~1308), verificar `_remaining_time() < self.config.min_time_for_gates_s + 60` (reserva 60s para simulação). Se insuficiente, logar `[Circuit Breaker] Tempo restante insuficiente para gates + simulação. Abortando.` e retornar `(True, 0.0)`
  - [x] SubTask 3.2: Após `_expand_child` retornar com sucesso (child != leaf) e antes de `_check_iteration_abort` (linha ~1318), verificar se o child tem `gate_ab_score > 0` e `gate_post_eval_score > 0`. Se sim, salvar checkpoint provisório com `child.gate_ab_score` e `child.gate_post_eval_score`, logando `[Checkpoint Provisório] Candidato gate-approved salvo: A/B={ab_score:.3f}, Post-Eval={post_score:.3f}`
  - [x] SubTask 3.3: No bloco `except concurrent.futures.TimeoutError` (linha ~1348-1354), ANTES do `return True, 0.0`, verificar se `child.gate_ab_score > 0` (indica que o candidato passou pelos gates). Se sim:
    - Definir `fallback_raw = child.gate_ab_score` (Gate A/B já usa `funcao_de_recompensa`, mesma escala do raw_reward)
    - Definir `child.raw_reward = fallback_raw`
    - Logar `[Gate Fallback] Simulação timeout. Usando fallback_raw={fallback_raw:.3f} do Gate A/B (score_mut={ab_score:.3f}). Post-Eval={post_score:.3f}`
    - Executar `_commit_iteration(child, fallback_raw, "fallback: simulação timeout, gate-approved")` 
    - Executar `_save_checkpoint(child, fallback_raw)`
    - Retornar `(False, fallback_raw)` em vez de `(True, 0.0)`
  - [x] SubTask 3.4: Garantir que `child.gate_ab_score` seja verificado APÓS `_evaluate_and_prune` — se a poda heurística removeu o nó, o fallback não se aplica

- [x] Task 4: Testes de validação
  - [x] SubTask 4.1: Teste unitário do time-gate preventivo — simular `_remaining_time() < min_time_for_gates_s + 60` e verificar que `_run_mcts_iteration` aborta ANTES de chamar `_expand_child`
  - [x] SubTask 4.2: Teste unitário do fallback — criar child com `gate_ab_score=0.465, gate_post_eval_score=0.650`, simular `TimeoutError` na simulação, verificar que `child.raw_reward = 0.465`, `_commit_iteration` foi chamado, e `_save_checkpoint` foi chamado
  - [x] SubTask 4.3: Teste unitário do checkpoint provisório — verificar que após `_expand_child` retornar child gate-approved, o checkpoint provisório é salvo com os scores corretos
  - [x] SubTask 4.4: Teste unitário de que fallback NÃO é aplicado quando `gate_ab_score == 0.0` (candidato não passou pelos gates)
  - [x] SubTask 4.5: Executar `test_optimizer.py`, `test_mcts.py`, `test_bandit.py`, `test_optimizer_integration.py` e verificar passagem sem regressão

# Task Dependencies
- Task 1 (campos no MCTSNode) é pré-requisito para Task 3 (fallback)
- Task 2 (config) é independente
- Task 3 (time-gate + fallback) depende de Task 1 e Task 2
- Task 4 (testes) depende de Tasks 1-3
