# Checklist

## Correção do Crash NoneType
- [x] `_discover_strategy` valida `nova_estrat.nome_estrategia` antes de chamar `.lower()` e retorna fallback sem crash quando é `None` ou vazio
- [x] Warning `[Discovery] nome_estrategia vazio/None, usando fallback` é emitido quando o campo é inválido
- [x] `DiscoveredStrategy.__post_init__` (se implementado) garante que `nome_estrategia` nunca seja `None`

## Circuit Breaker Preventivo
- [x] Em `_discover_strategy`, `self._remaining_time()` é verificado **antes** de `self._llm_executor.submit()`
- [x] Em `_try_generate_mutation`, `self._remaining_time()` é verificado **antes** de `self._llm_executor.submit()`
- [x] Em `_run_mcts_iteration`, `self._remaining_time()` é verificado **antes** de `simulation_executor.submit()`
- [x] Chamadas inúteis a `future.cancel()` nos handlers de `TimeoutError` foram removidas
- [x] Quando deadline passou, o log declara `[Circuit Breaker] Deadline já passado, abortando submissão` (não "Cancelamento solicitado=False")

## Preservação de `strat` no Log
- [x] `_last_iter_strategy` é atribuído com `child.mutation_strategy` imediatamente após `_expand_child`, antes de `_check_iteration_abort()` no checkpoint 2
- [x] `_last_iter_depth` é atribuído com `child.depth` no mesmo ponto
- [x] Quando circuit breaker dispara após expansão, o log mostra `strat=<estratégia real>` em vez de `strat=N/A`

## Abort Imediato de Batch
- [x] `_run_single_iteration` verifica `_remaining_time()` no início de cada iteração do batch
- [x] Quando deadline esgotado, log `[Batch Abort] Deadline esgotado, pulando iterações X-Y` é emitido
- [x] Iterações restantes são puladas sem chamar `_run_mcts_iteration`
- [x] Sumário final de iterações não é corrompido pelo `break` antecipado

## Testes
- [x] `test_optimizer.py` passa sem regressões
- [x] `test_mcts.py` passa sem regressões
- [x] `test_bandit.py` passa sem regressões
- [x] `test_optimizer_integration.py` passa sem regressões
- [x] Novo teste do crash NoneType passa
- [x] Novo teste do circuit breaker preventivo passa
- [x] Novo teste da preservação de strat passa
- [x] Novo teste do abort de batch passa
