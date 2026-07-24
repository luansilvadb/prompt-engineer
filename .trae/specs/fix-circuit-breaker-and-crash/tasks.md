# Tasks

- [x] Task 1: Corrigir crash `NoneType` em `_discover_strategy`
  - [x] SubTask 1.1: Em `src/optimizer.py:444`, antes de `key_raw = nova_estrat.nome_estrategia.lower()`, adicionar validação: `if not nova_estrat.nome_estrategia:` → emitir warning `[Discovery] nome_estrategia vazio/None, usando fallback` e retornar `fallback_keys[0]`
  - [x] SubTask 1.2: (Opcional) Adicionar `__post_init__` no dataclass `DiscoveredStrategy` em `src/domain/agent_interfaces.py` que converte `nome_estrategia` para string vazia se for `None`, como defesa em profundidade

- [x] Task 2: Tornar circuit breaker preventivo — verificar deadline antes de `executor.submit()`
  - [x] SubTask 2.1: Em `_discover_strategy` (linhas 405-423), mover a verificação `remaining_time = self._remaining_time(self.config.llm_timeout)` para **antes** de `executor.submit()`. Se `remaining_time <= 0`, não submeter, setar `_iteration_circuit_broken = True`, logar `[Circuit Breaker] Deadline já passado, abortando submissão de discovery`, e retornar `fallback_keys[0]`
  - [x] SubTask 2.2: Em `_try_generate_mutation` (linhas 514-542), verificar `remaining_time = self._remaining_time(self.config.llm_timeout)` **antes** de `executor.submit()`. Se `remaining_time <= 0`, setar `_iteration_circuit_broken = True`, logar, e retornar `None`
  - [x] SubTask 2.3: Em `_run_mcts_iteration` (linhas 1348-1361), verificar `remaining = self._remaining_time(1.0)` **antes** de `simulation_executor.submit()`. Se `remaining <= 0`, tratar como `TimeoutError` (setar `_iteration_circuit_broken`, retornar `True, 0.0`)
  - [x] SubTask 2.4: Remover chamadas inúteis a `future.cancel()` nos handlers de `TimeoutError` (linhas 413-415, 556-568, 1354-1361), substituindo por log declarando que a thread continuará em background mas o resultado será descartado

- [x] Task 3: Preservar `_last_iter_strategy` antes do checkpoint de abort
  - [x] SubTask 3.1: Em `_run_mcts_iteration`, mover as atribuições `self._last_iter_strategy = child.mutation_strategy or 'unknown'` e `self._last_iter_depth = child.depth` para imediatamente após `child = self._expand_child(leaf)` (linha ~1314), antes do `finally` e antes do checkpoint 2 de `_check_iteration_abort()`
  - [x] SubTask 3.2: Garantir que a atribuição usa `child.mutation_strategy` (que é populada por `_expand_node`), não o valor default `'N/A'`

- [x] Task 4: Abort imediato de batch sem orçamento
  - [x] SubTask 4.1: Em `_run_single_iteration` (loop `for i in range(self.config.max_iterations)`), adicionar verificação `if self._remaining_time(1.0) <= 0:` no início de cada iteração. Se verdadeiro, logar `[Batch Abort] Deadline esgotado, pulando iterações {i+1}-{max_iterations}`, setar `_iteration_circuit_broken = True`, e `break`
  - [x] SubTask 4.2: Garantir que o `break` do batch abort não interfere no sumário final de iterações (métricas de `_iteration_count`, `_iteration_rewards`, etc.)

- [x] Task 5: Testes de validação
  - [x] SubTask 5.1: Teste unitário do crash NoneType — simular `DiscoveredStrategy(nome_estrategia=None, ...)` e verificar que `_discover_strategy` retorna fallback sem crash
  - [x] SubTask 5.2: Teste unitário do circuit breaker preventivo — mockar `_remaining_time` retornando 0 e verificar que `executor.submit()` NÃO é chamado em `_discover_strategy` e `_try_generate_mutation`
  - [x] SubTask 5.3: Teste unitário da preservação de strat — mockar `_check_iteration_abort` retornando `True` após `_expand_child` e verificar que `_last_iter_strategy` reflete `child.mutation_strategy`
  - [x] SubTask 5.4: Teste unitário do abort de batch — mockar `_remaining_time` retornando 0 a partir da iteração 3 e verificar que iterações 3+ são puladas
  - [x] SubTask 5.5: Executar `test_optimizer.py`, `test_mcts.py`, `test_bandit.py`, `test_optimizer_integration.py` e verificar passagem sem regressão

# Task Dependencies
- Task 1 (crash NoneType) é independente
- Task 2 (circuit breaker preventivo) é independente
- Task 3 (preservação de strat) é independente
- Task 4 (abort de batch) é independente das demais, mas complementa Task 2
- Task 5 (testes) depende de Tasks 1-4
