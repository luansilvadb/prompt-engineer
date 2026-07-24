# Correção de Circuit Breaker Cosméticos e Crash de NoneType (Rodada 3) Spec

## Why
A Rodada 2 (`fix-structural-bugs-round-2`) corrigiu dois problemas graves (guarda anti-regressão e coordenação entre threads), mas introduziu um crash novo (`'NoneType' object has no attribute 'lower'`) e o circuit breaker continua sendo cosmético em vez de preventivo — ele detecta estouro de deadline mas não interrompe chamadas LLM em andamento. O resultado prático foi o pior custo já registrado: 31 minutos e dezenas de chamadas LLM para, ao final, devolver a instrução original inalterada. Além disso, o log perde informação de diagnóstico (`strat=N/A`) em iterações onde o circuit breaker dispara após a expansão.

## What Changes
- **Correção do crash `NoneType`**: validar `nome_estrategia` antes de chamar `.lower()` em `src/optimizer.py:444`, com fallback seguro quando o LLM retorna campo vazio ou `None`
- **Circuit breaker verdadeiramente preventivo**: mover a verificação de `_remaining_time()` para **antes** de `executor.submit()` em `_discover_strategy`, `_try_generate_mutation`, e `_run_mcts_iteration`; usar `_remaining_time()` como timeout no `future.result()` para que o `TimeoutError` seja lançado pelo próprio `future.result()` (não por polling externo), e tratar `TimeoutError` sem tentar `future.cancel()` (que é inútil para threads em execução)
- **Preservação de `strat` no log**: mover a atribuição de `_last_iter_strategy` para imediatamente após `_expand_child`, antes do checkpoint 2 do circuit breaker, para que o log sempre reflita a estratégia real usada na expansão
- **Abort imediato ao entrar em iteração sem orçamento**: `_check_iteration_abort` já verifica `_remaining_time()`, mas as iterações subsequentes do batch ainda tentam gerar do zero antes de descobrir que não há orçamento; ajustar `_run_single_iteration` para verificar `_remaining_time()` antes de chamar `_run_mcts_iteration` e pular iterações restantes do batch quando o orçamento já está esgotado

## Impact
- Affected specs: `fix-structural-bugs-round-2` (circuit breaker da rodada 2 não foi suficiente), `fix-mcts-performance` (tempo de execução)
- Affected code:
  - `src/optimizer.py` — linhas 405-423 (`_discover_strategy`), 514-568 (`_try_generate_mutation`), 1303-1332 (`_run_mcts_iteration`), 1400-1450 (`_run_single_iteration`), 444 (`_discover_strategy` — crash `.lower()`)
  - `src/domain/agent_interfaces.py` — `DiscoveredStrategy` dataclass (opcional: validação no `__post_init__`)
  - `tests/` — testes para crash NoneType, circuit breaker preventivo, preservação de strat, abort imediato de batch

## ADDED Requirements

### Requirement: Validação de `nome_estrategia` contra None
O sistema SHALL validar que `nova_estrat.nome_estrategia` não é `None` ou string vazia antes de chamar `.lower()` em `_discover_strategy`, tratando o caso com fallback seguro (log de warning + fallback para estratégia padrão) em vez de crash.

#### Scenario: LLM retorna nome None
- **WHEN** o `strategy_discoverer` do DSPy retorna `DiscoveredStrategy` com `nome_estrategia=None`
- **THEN** `_discover_strategy` emite warning `[Discovery] nome_estrategia vazio/None, usando fallback`, não crasha com `AttributeError`, e retorna `fallback_keys[0]` como se a descoberta tivesse falhado

#### Scenario: LLM retorna nome vazio
- **WHEN** o `strategy_discoverer` retorna `nome_estrategia=""`
- **THEN** mesmo comportamento: warning + fallback, sem crash

### Requirement: Submissão Condicional ao Deadline (Circuit Breaker Preventivo)
O sistema SHALL verificar `_remaining_time() > 0` **antes** de cada `executor.submit()`, e não submeter novas chamadas LLM quando o deadline já passou. O `future.result(timeout=...)` deve usar o `_remaining_time()` como timeout, e o `TimeoutError` deve ser tratado como falha recuperável sem tentar `future.cancel()`.

#### Scenario: Deadline já passou antes de submit
- **WHEN** `_discover_strategy` ou `_try_generate_mutation` é chamado e `_remaining_time(llm_timeout) <= 0`
- **THEN** nenhum `executor.submit()` é feito, o log declara `[Circuit Breaker] Deadline já passado, abortando submissão`, a flag `_iteration_circuit_broken = True` é setada, e a função retorna fallback ou `None`

#### Scenario: Timeout durante execução da chamada LLM
- **WHEN** `future.result(timeout=remaining)` lança `TimeoutError`
- **THEN** o log declara `[Circuit Breaker] Timeout após {remaining}s`, `_iteration_circuit_broken = True` é setado, **não** se chama `future.cancel()` (inútil para thread em execução), e a função retorna fallback

### Requirement: Preservação de `_last_iter_strategy` Antes do Checkpoint de Abort
O sistema SHALL atribuir `_last_iter_strategy` e `_last_iter_depth` imediatamente após `_expand_child` retornar, **antes** do checkpoint 2 de `_check_iteration_abort()`, para que o log de iteração sempre reflita a estratégia real usada na expansão.

#### Scenario: Circuit breaker dispara após expansão bem-sucedida
- **WHEN** `_expand_child` completa com sucesso (estratégia X usada, child criado), e em seguida `_check_iteration_abort()` retorna `True`
- **THEN** `_last_iter_strategy` já contém o nome da estratégia X (atribuído logo após `_expand_child`), e o log mostra `strat=X` em vez de `strat=N/A`

### Requirement: Abort Imediato de Batch sem Orçamento
O sistema SHALL verificar `_remaining_time()` no início de `_run_single_iteration` e pular iterações restantes do batch quando o orçamento de tempo já está esgotado, em vez de entrar em `_run_mcts_iteration` que fará a mesma verificação internamente.

#### Scenario: Batch de 10 iterações, deadline estourado na iteração 5
- **WHEN** a iteração 5 do batch consome todo o `iteration_timeout_s`, e as iterações 6-10 ainda estão pendentes
- **THEN** `_run_single_iteration` verifica `_remaining_time()` antes de cada iteração, e para as iterações 6-10 emite log `[Batch Abort] Deadline esgotado, pulando iterações 6-10` e retorna imediatamente sem chamar `_run_mcts_iteration`

## MODIFIED Requirements
(Nenhum requisito modificado nesta fase)

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
