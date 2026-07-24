# Tasks

- [x] Task 1: Salvar checkpoint incremental após aprovação do Gate A/B
  - [x] SubTask 1.1: No `_expand_node`, após o bloco `if delta_ab >= margem_minima:` (Gate A/B aprovou) e **antes** do bloco do Post-Eval, chamar um novo método `_save_incremental_checkpoint(child, stage="gate_ab", score=score_mut)`
  - [x] SubTask 1.2: Implementar `_save_incremental_checkpoint` que armazena em `self._incremental_checkpoint` um dicionário com `{node_id, instruction, strategy, gate_ab_score, gate_post_eval_score, stage, timestamp}`
  - [x] SubTask 1.3: Emitir log `[Checkpoint Incremental] Gate A/B aprovado: score={score}, strat={strategy}`

- [x] Task 2: Atualizar checkpoint incremental após aprovação do Post-Eval
  - [x] SubTask 2.1: No `_expand_node`, após o bloco `if delta_post >= margem_minima:` (Post-Eval aprovou), chamar `_save_incremental_checkpoint(child, stage="post_eval", score=post_score_mut)` que **atualiza** o registro existente (não cria um novo)
  - [x] SubTask 2.2: Emitir log `[Checkpoint Incremental] Post-Eval aprovado: score={post_score} (completo: A/B={ab_score}, Post-Eval={post_score})`

- [x] Task 3: Usar `gate_ab_score` como proxy na guarda anti-regressão final
  - [x] SubTask 3.1: Em `_run_mcts_loop`, no bloco da guarda anti-regressão final (onde compara `best_node.raw_reward` vs `root.raw_reward`), adicionar fallback: se `best_node.raw_reward == 0.0` e `best_node.gate_ab_score > 0`, usar `comparison_value = best_node.gate_ab_score` e logar `[Guarda Anti-Regressão] Usando gate_ab_score={value} como proxy (checkpoint incompleto)`
  - [x] SubTask 3.2: Garantir que `best_node` carrega `gate_ab_score` do checkpoint (pode exigir que `_save_checkpoint` / `_load_best_checkpoint` serialize/deserialize `gate_ab_score`)

- [x] Task 4: Checkpoint incremental para `__DISCOVER__`
  - [x] SubTask 4.1: Em `_discover_strategy`, após a descoberta bem-sucedida (antes do `return` com sucesso), salvar a estratégia descoberta via `_save_incremental_checkpoint` com `stage="discovery"` e os metadados da estratégia (nome, eixo, prompt)
  - [x] SubTask 4.2: Emitir log `[Checkpoint Incremental] Descoberta salva: strat={nome}, eixo={eixo}`

- [x] Task 5: Testes de validação
  - [x] SubTask 5.1: Teste unitário — simular Gate A/B aprovando e circuit breaker disparando antes do Post-Eval; verificar que checkpoint incremental foi salvo com `stage="gate_ab"` e `gate_ab_score` correto
  - [x] SubTask 5.2: Teste unitário — simular ambos os gates aprovando; verificar que checkpoint incremental foi atualizado com `stage="post_eval"` e ambos os scores
  - [x] SubTask 5.3: Teste unitário — simular `best_node.raw_reward=0.0, gate_ab_score=0.299` na guarda final; verificar que a comparação usa `0.299` (não `0.0`) e o log declara "proxy"
  - [x] SubTask 5.4: Teste unitário — simular descoberta bem-sucedida seguida de abort; verificar checkpoint incremental com `stage="discovery"`
  - [x] SubTask 5.5: Executar `test_optimizer.py`, `test_mcts.py`, `test_bandit.py`, `test_optimizer_integration.py` e verificar passagem sem regressão

# Task Dependencies
- Task 2 depende de Task 1 (atualiza o mesmo mecanismo de checkpoint incremental)
- Task 3 depende de Task 1 (precisa que `gate_ab_score` esteja salvo no checkpoint)
- Task 4 é independente
- Task 5 depende de Tasks 1-4
