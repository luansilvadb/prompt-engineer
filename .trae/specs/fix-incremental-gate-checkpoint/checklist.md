# Checklist

## Checkpoint Incremental Pós-Gate A/B
- [x] Após aprovação do Gate A/B e antes do Post-Eval, `_save_incremental_checkpoint` é chamado com `stage="gate_ab"`
- [x] O checkpoint armazena `{node_id, instruction, strategy, gate_ab_score, stage, timestamp}`
- [x] O log declara `[Checkpoint Incremental] Gate A/B aprovado: score={score}, strat={strategy}`
- [x] Se o Gate A/B reprova, NENHUM checkpoint incremental é salvo

## Atualização do Checkpoint Incremental Pós-Post-Eval
- [x] Após aprovação do Post-Eval, `_save_incremental_checkpoint` é chamado com `stage="post_eval"` e ATUALIZA o registro existente
- [x] O log declara `[Checkpoint Incremental] Post-Eval aprovado: score={post_score} (completo: A/B={ab_score}, Post-Eval={post_score})`
- [x] Se o Post-Eval reprova, o checkpoint incremental do Gate A/B é descartado

## Guarda Anti-Regressão com `gate_ab_score` como Proxy
- [x] Quando `best_node.raw_reward == 0.0` e `best_node.gate_ab_score > 0`, a guarda usa `gate_ab_score` para comparação
- [x] O log declara `[Guarda Anti-Regressão] Usando gate_ab_score={value} como proxy (checkpoint incompleto)`
- [x] Quando `best_node.raw_reward > 0`, comportamento atual é mantido (compara `raw_reward`)
- [x] `gate_ab_score` é serializado/deserializado corretamente no checkpoint persistente

## Checkpoint Incremental para `__DISCOVER__`
- [x] Após `_discover_strategy` retornar com sucesso, checkpoint incremental é salvo com `stage="discovery"`
- [x] O log declara `[Checkpoint Incremental] Descoberta salva: strat={nome}, eixo={eixo}`
- [x] Estratégias descobertas e salvas incrementalmente estão disponíveis para a próxima execução

## Cenário End-to-End: Candidato Perdido Entre Gates Não Some
- [x] Com Gate A/B aprovando (score=0.299, delta=+0.106) e circuit breaker disparando antes do Post-Eval:
  - [x] `[Checkpoint Incremental] Gate A/B aprovado: score=0.299` aparece no log
  - [x] O candidato não some completamente — está registrado no checkpoint incremental
  - [x] O `[ITER]` correspondente não mostra `strat=none | raw=0.000` se o checkpoint incremental existe
- [x] Com ambos os gates aprovando e simulação timeout:
  - [x] Checkpoint incremental mostra `stage="post_eval"` com ambos os scores
  - [x] Fallback da spec `fix-checkpoint-race-condition` ainda funciona (sem regressão)

## Testes
- [x] `test_optimizer.py` passa sem regressões (18/18: 12 existentes + 6 novos)
- [x] `test_mcts.py` passa sem regressões (6/6)
- [x] `test_bandit.py` passa sem regressões (27/28 — 1 falha pré-existente em `test_select_syncs_new_registry_keys_before_choosing`, não relacionada a esta spec)
- [x] `test_optimizer_integration.py` passa sem regressões (4/4)
- [x] Novo teste de checkpoint incremental pós-Gate A/B passa
- [x] Novo teste de atualização pós-Post-Eval passa
- [x] Novo teste de guarda com gate_ab_score proxy passa
- [x] Novo teste de checkpoint de discovery passa
