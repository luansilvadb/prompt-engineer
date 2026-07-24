# Checklist

## Campos de Gate Score no MCTSNode
- [x] `MCTSNode` possui campos `gate_ab_score: float = 0.0` e `gate_post_eval_score: float = 0.0`
- [x] No fluxo de estratégia composta, `child.gate_ab_score = score_mut` e `child.gate_post_eval_score = post_score_mut` são definidos antes do `return child`
- [x] No fluxo de estratégia isolada, `child.gate_ab_score = score_mut` e `child.gate_post_eval_score = post_score_mut` são definidos antes do `return child`
- [x] `merge_stats` preserva o maior `gate_ab_score` e `gate_post_eval_score` entre os nós mergeados

## Parâmetro `min_time_for_gates_s`
- [x] `min_time_for_gates_s: float = 10.0` existe no `MCTSConfig` com validação `[1.0, 60.0]`
- [x] `MCTS_MIN_TIME_FOR_GATES_S` é respeitada como variável de ambiente
- [x] Valor inválido (< 1.0 ou > 60.0) lança `ValueError`

## Time-Gate Preventivo
- [x] Antes de `_expand_child`, o sistema verifica `_remaining_time() >= min_time_for_gates_s + 60` e aborta com log se insuficiente
- [x] O abort ocorre ANTES de qualquer chamada LLM dos gates (Gate A/B, Post-Eval)
- [x] O log declara `[Circuit Breaker] Tempo restante insuficiente para gates + simulação. Abortando.`

## Checkpoint Provisório
- [x] Após `_expand_child` retornar child != leaf com `gate_ab_score > 0`, o checkpoint provisório é salvo
- [x] O log declara `[Checkpoint Provisório] Candidato gate-approved salvo: A/B={score}, Post-Eval={score}`
- [x] Se a simulação completa com sucesso, o checkpoint definitivo sobrescreve o provisório

## Fallback para Timeout de Simulação
- [x] Quando `future.result(timeout=remaining)` lança `TimeoutError` E `child.gate_ab_score > 0`, o fallback é aplicado
- [x] `fallback_raw = child.gate_ab_score` (escala compatível com raw_reward pois Gate A/B usa `funcao_de_recompensa`)
- [x] `child.raw_reward = fallback_raw` é definido antes de `_commit_iteration`
- [x] `_commit_iteration(child, fallback_raw, ...)` é chamado com feedback de fallback
- [x] `_save_checkpoint(child, fallback_raw)` é chamado
- [x] O retorno é `(False, fallback_raw)` (não `(True, 0.0)`) — iteração conta como produtiva
- [x] O log declara `[Gate Fallback] Simulação timeout. Usando fallback_raw={value} do Gate A/B`
- [x] Quando NÃO há gate_ab_score (> 0), o comportamento atual é mantido: `return True, 0.0`
- [x] O fallback NÃO é aplicado se `_evaluate_and_prune` removeu o nó (heuristic pruning ocorreu antes)

## Cenário End-to-End: Iteração 7 Não Perde Candidato Aprovado
- [x] Com `variacao_tom` aprovado por ambos os gates (+0.272 A/B, +0.650 Post-Eval), se a simulação sofre timeout:
  - [x] `child.raw_reward = 0.465` (score_mut do Gate A/B, não 0.0)
  - [x] `[Gate Fallback]` é logado com os scores corretos
  - [x] `[Checkpoint] Melhor nó salvo` é logado (via `_save_checkpoint`)
  - [x] `_commit_iteration` executa, atualizando bandit e experience store
  - [x] O `[ITER 7/10]` mostra `raw=0.465` (não 0.000)
  - [x] A guarda anti-regressão final compara `best_node.raw_reward=0.465` contra `root.raw_reward=0.657`

## Testes
- [x] `test_optimizer.py` passa sem regressões (12/12: 8 existentes + 4 novos)
- [x] `test_mcts.py` passa sem regressões (6/6)
- [x] `test_bandit.py` passa sem regressões (27/28 — 1 falha pré-existente em `test_select_syncs_new_registry_keys_before_choosing`, não relacionada a esta spec)
- [x] `test_optimizer_integration.py` passa sem regressões (4/4)
- [x] Novo teste do time-gate preventivo passa
- [x] Novo teste do fallback com gate scores passa
- [x] Novo teste do checkpoint provisório passa
- [x] Novo teste de que fallback NÃO aplica sem gate_ab_score passa
