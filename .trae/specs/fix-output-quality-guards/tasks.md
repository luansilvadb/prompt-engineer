# Tasks

- [x] Task 1: Implementar guarda anti-regressão na seleção final
  - [x] SubTask 1.1: Modificar `_select_and_log_best_node` para retornar também o score da raiz como referência
  - [x] SubTask 1.2: Modificar `_format_best_node` para comparar `best_node.score` com `root_score` e, se `best_node.score < root_score`, retornar `root.instruction` com WARNING explícito
  - [x] SubTask 1.3: Garantir que `optimize()` retorna a instrução original quando nenhum filho supera a raiz

- [x] Task 2: Adicionar transparência na cadeia de score
  - [x] SubTask 2.1: Adicionar campos `raw_reward`, `multiplied_reward`, `shaped_reward` ao `MCTSNode` para armazenar a cadeia completa
  - [x] SubTask 2.2: Modificar `_run_mcts_iteration` para capturar `raw_reward` antes dos multipliers e registrar `multiplied_reward` após `_apply_reward_multipliers`
  - [x] SubTask 2.3: Modificar `_commit_iteration` para registrar `shaped_reward` no nó antes do backpropagation
  - [x] SubTask 2.4: Emitir log `[Score Chain]` ao final de cada iteração com a cadeia completa: raw → mult → shaped → Q/visits

- [x] Task 3: Diversificar prompt do `__DISCOVER__` e despriorizar estratégias monocultura
  - [x] SubTask 3.1: Enriquecer `_discover_strategy` com exemplos concretos dos 5 eixos de mutação no prompt enviado ao LLM
  - [x] SubTask 3.2: Adicionar instrução explícita no prompt: "Gere uma estratégia de um eixo DIFERENTE dos já listados"
  - [x] SubTask 3.3: Implementar tracking de sucesso/falha por estratégia descoberta e, após 3 falhas consecutivas (0% de sucesso), reduzir prior no bandit

- [x] Task 4: Tornar gates de qualidade explícitos sobre incerteza
  - [x] SubTask 4.1: Modificar `_run_ab_gate` para emitir WARNING (não só INFO) quando `test_cases` está vazio, com mensagem de incerteza alta
  - [x] SubTask 4.2: Modificar `_run_post_eval` para emitir WARNING quando `test_cases` está vazio
  - [x] SubTask 4.3: Adicionar contadores `gates_without_test_cases` e `post_evals_without_test_cases` no Optimizer e logá-los nas estatísticas finais

- [x] Task 5: Implementar recompensa gradual para quebra de contrato
  - [x] SubTask 5.1: Modificar `funcao_de_recompensa` em `src/signatures.py` para substituir `return 0.0` binário por penalty gradual: `max(0.05, composite_score - min(len(defeitos) * 0.20, 0.80))`
  - [x] SubTask 5.2: Adicionar log informando quantas violações causaram a penalidade e o score resultante
  - [x] SubTask 5.3: Manter `manteve_regras_criticas=False` como sinal forte no feedback, mas com score > 0 para preservar gradiente MCTS

- [x] Task 6: Fazer plateau abort cancelar futures do batch corrente
  - [x] SubTask 6.1: Modificar `_run_threaded_search` para, ao receber `should_break=True`, chamar `executor.shutdown(wait=False, cancel_futures=True)` e logar quantas iterações foram canceladas
  - [x] SubTask 6.2: Adicionar verificação de `self._abort_flag` no início de `_run_single_iteration` (antes de chamar `_run_mcts_iteration`) para early exit
  - [x] SubTask 6.3: Garantir que o loop principal não submete novo batch quando `_abort_flag` está setado

# Task Dependencies
- Task 1 (guarda anti-regressão) e Task 2 (transparência de score) são independentes e podem rodar em paralelo
- Task 3 (diversificar __DISCOVER__) é independente das demais
- Task 4 (gates com incerteza) é independente das demais
- Task 5 (recompensa gradual) é independente das demais
- Task 6 (plateau abort) é independente das demais
- Todas as 6 tasks podem ser executadas em paralelo
