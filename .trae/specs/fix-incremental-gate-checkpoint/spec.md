# Checkpoint Incremental por Estágio de Gate Spec

## Why
A spec `fix-checkpoint-race-condition` resolveu o caso em que **ambos os gates aprovam** mas a simulação sofre timeout — usando fallback via `gate_ab_score`. Porém, a race condition persiste em um cenário mais granular: quando o Gate A/B aprova um candidato mas o circuit breaker dispara **antes** do Post-Eval Comportamental executar. Neste caso, o candidato é perdido completamente — sem `[Post-Eval]`, sem `[Checkpoint]`, sem entrada no `[ITER]`. O log mostra apenas `[Gate A/B] ... APROVADO` seguido de silêncio, e a iteração termina com `strat=none | raw=0.000`.

A raiz do problema é que o checkpoint atual é "tudo ou nada": só salva após simulação completa (ou, com o fallback da spec anterior, após ambos os gates + timeout de simulação). Mas entre os gates não há checkpoint algum. O candidato que passou pelo Gate A/B já representa trabalho de LLM investido e uma aprovação real — precisa ser preservado mesmo que o resto da iteração seja abortada.

## What Changes
- **Checkpoint incremental pós-Gate A/B**: após a aprovação do Gate A/B (antes de executar o Post-Eval), salvar um checkpoint incremental com `gate_ab_score`, a instrução do candidato, e a estratégia usada. Se o circuit breaker disparar antes do Post-Eval, este checkpoint serve como ancoragem mínima.
- **Atualização do checkpoint pós-Post-Eval**: após a aprovação do Post-Eval, atualizar o checkpoint incremental com `gate_post_eval_score`. Se ambos os gates aprovarem mas a simulação der timeout, o fallback já existente (`fix-checkpoint-race-condition`) cobre o resto.
- **Inclusão do gate_ab_score na guarda anti-regressão final**: quando o melhor nó do checkpoint tem `raw_reward=0.0` (checkpoint "incompleto", só Gate A/B), o `gate_ab_score` deve ser usado como proxy para comparação com a raiz, em vez de descartar o candidato como pior.
- **Checkpoint incremental para `__DISCOVER__`**: a fase de descoberta também tem seu próprio timeout (`[Circuit Breaker] Descoberta excedeu timeout`). Resultados de descoberta que completam mas não chegam a ser registrados por abort pós-descoberta devem ser salvos incrementalmente ao final da chamada de discovery.
- **Log explícito de checkpoint incremental**: `[Checkpoint Incremental] Gate A/B aprovado: score={ab_score}, strat={strategy}` e `[Checkpoint Incremental] Post-Eval aprovado: score={post_score}`.

## Impact
- Affected specs: `fix-checkpoint-race-condition` (complementa o fallback com checkpoints entre gates), `fix-circuit-breaker-and-crash` (circuit breaker agora não consegue mais "matar" candidatos entre estágios de gate), `fix-structural-bugs-round-2` (a diversificação de estratégias gera mais cenários onde o gap entre gates importa)
- Affected code:
  - `src/optimizer.py` — `_run_mcts_iteration`: salvar checkpoint incremental após cada estágio de gate, usar `gate_ab_score` na guarda final quando `raw_reward=0.0`
  - `src/optimizer.py` — `_expand_node`: expor `score_mut` do Gate A/B individualmente (já existe como `gate_ab_score` no MCTSNode, mas precisa ser salvo no checkpoint incremental)
  - `src/optimizer.py` — `_discover_strategy`: salvar checkpoint incremental ao final da descoberta bem-sucedida
  - `src/domain/mcts.py` — `MCTSNode`: possivelmente adicionar flag `gate_ab_only: bool = False` para marcar nós com checkpoint incompleto
  - `src/domain/config.py` — sem novos parâmetros necessários (reusa `min_time_for_gates_s`)

## ADDED Requirements

### Requirement: Checkpoint Incremental Pós-Gate A/B
O sistema SHALL salvar um checkpoint imediatamente após a aprovação do Gate A/B, antes de executar o Post-Eval Comportamental, preservando o `gate_ab_score`, a instrução do candidato, e a estratégia usada.

#### Scenario: Circuit breaker dispara entre Gate A/B e Post-Eval
- **WHEN** o Gate A/B aprova um candidato com `score_mut=0.299` e delta `+0.106`, mas o circuit breaker dispara (`_remaining_time() < min_time_for_gates_s`) antes do Post-Eval executar
- **THEN** o checkpoint incremental pós-Gate A/B já foi salvo, o log mostra `[Checkpoint Incremental] Gate A/B aprovado: score=0.299, strat=variacao_tom`, e o candidato não é completamente perdido (existe no registro do checkpoint)

#### Scenario: Gate A/B reprova
- **WHEN** o Gate A/B reprova uma mutação
- **THEN** nenhum checkpoint incremental é salvo (comportamento atual mantido)

### Requirement: Atualização do Checkpoint Incremental Pós-Post-Eval
O sistema SHALL atualizar o checkpoint incremental após a aprovação do Post-Eval Comportamental, adicionando `gate_post_eval_score` ao registro existente.

#### Scenario: Ambos os gates aprovam, simulação timeout
- **WHEN** o Gate A/B e o Post-Eval aprovam, mas a simulação sofre timeout
- **THEN** o checkpoint incremental foi atualizado com ambos os scores, o fallback da spec `fix-checkpoint-race-condition` é aplicado (já existente), e o checkpoint definitivo é salvo com `raw=fallback_raw`

#### Scenario: Post-Eval reprova
- **WHEN** o Post-Eval reprova após Gate A/B ter aprovado
- **THEN** o checkpoint incremental do Gate A/B é descartado (ou marcado como obsoleto), e a falha é contada normalmente

### Requirement: Uso do `gate_ab_score` na Guarda Anti-Regressão Final
O sistema SHALL usar `gate_ab_score` como proxy de qualidade quando o melhor nó do checkpoint tem `raw_reward=0.0` mas `gate_ab_score > 0`, permitindo que candidatos com checkpoint incompleto (só Gate A/B) sejam considerados na decisão final.

#### Scenario: Melhor checkpoint só tem Gate A/B
- **WHEN** o melhor nó do checkpoint tem `raw_reward=0.0` e `gate_ab_score=0.299`
- **THEN** a guarda anti-regressão compara `gate_ab_score` contra `root.raw_reward` (em vez de `raw_reward=0.0`), e o log declara `[Guarda Anti-Regressão] Usando gate_ab_score={value} como proxy (checkpoint incompleto, sem simulação)`

#### Scenario: Melhor checkpoint tem simulação completa
- **WHEN** o melhor nó do checkpoint tem `raw_reward > 0`
- **THEN** comportamento atual é mantido: compara `raw_reward` contra `root.raw_reward`

### Requirement: Checkpoint Incremental para `__DISCOVER__`
O sistema SHALL salvar um checkpoint incremental ao final de uma chamada de `__DISCOVER__` bem-sucedida, preservando a estratégia descoberta mesmo que o circuit breaker dispare após a descoberta mas antes do registro.

#### Scenario: Descoberta bem-sucedida mas iteração abortada em seguida
- **WHEN** `_discover_strategy` retorna uma nova estratégia com sucesso, mas `_check_iteration_abort()` retorna `True` antes de `_expand_child` ser chamado
- **THEN** a estratégia descoberta é salva em checkpoint incremental com log `[Checkpoint Incremental] Descoberta salva: strat={nome}, eixo={eixo}`, e estará disponível para a próxima execução (não é perdida)

## MODIFIED Requirements

### Requirement: Ordem de Operações em `_run_mcts_iteration` (Ampliada)
A ordem estabelecida em `fix-checkpoint-race-condition` é ampliada para incluir checkpoints incrementais:

1. Selection + Expansion (já existente)
2. **Time-gate preventivo**: verificar `_remaining_time() >= min_time_for_gates_s` antes dos gates
3. Gate A/B (dentro de `_expand_node`, já existente)
4. **Após Gate A/B aprovar: salvar checkpoint incremental com `gate_ab_score`**
5. Post-Eval Comportamental (dentro de `_expand_node`, já existente)
6. **Após Post-Eval aprovar: atualizar checkpoint incremental com `gate_post_eval_score`**
7. Verificar `_remaining_time()` antes da simulação
8. Simulação com `future.result(timeout=remaining)`
9. Se timeout + gates aprovaram: fallback (já existente)
10. `_commit_iteration` + `_save_checkpoint`

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
