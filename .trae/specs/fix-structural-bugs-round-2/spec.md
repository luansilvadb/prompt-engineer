# Correção de Bugs Estruturais Persistentes (Rodada 2) Spec

## Why
Após as rodadas anteriores (`fix-score-scale-consistency`, `fix-mcts-performance`, `fix-optimizer-log-issues`, `add-mutation-gate-composition`), a infraestrutura de observabilidade e gates está genuinamente melhor, mas persistem seis bugs estruturais visíveis no log de execução: (1) o "Circuit Breaker" de 300s é post-mortem (regista a violação depois dela acontecer, não interrompe a chamada LLM em andamento); (2) o `shaped_reward` fica abaixo do `raw_reward` por erro de escala no `parent_reward` usado no shaping (usa `multiplied` em vez de `raw`), criando uma "penalidade fantasma" que anula o bônus declarado; (3) a poda relativa mistura escalas não-validadas; (4) threads paralelas no mesmo batch expandem o mesmo nó com a mesma estratégia sem coordenação pré-LLM, desperdiçando tokens; (5) o prior boosting hardcoded do `mutador_cognitivo` sempre aplica `mean_delta=0.05` mesmo quando a memória experiencial registra `mean_delta=-0.582`, contradizendo a própria memória; (6) a eficiência de expansão travou em 15.8% por monocultura de mutações e possível dupla contagem de falhas.

## What Changes
- **Circuit Breaker preemptivo**: o teto de tempo da iteração (`iteration_timeout_s`) passa a ser imposto via `concurrent.futures` com `future.result(timeout=...)` e `future.cancel()` na chamada de simulação, e o `_check_iteration_abort` passa a ser consultado também via relógio compartilhado antes de submeter novas chamadas LLM. O teto passaa cancelar futures pendentes, não apenas logar.
- **Shaping com escala consistente**: `_commit_iteration` passa a usar `child.parent.raw_reward` (em vez de `child.parent.last_reward` que é `multiplied_reward`) como `parent_reward` em `calcular_delta_reward`, e `last_reward` passa a armazenar `raw_reward` (não `multiplied_reward`) para manter coerência de escala ao longo do DAG. O log `[Score Chain]` passa a revelar o `parent_reward` e a escala usada.
- **Poda relativa com escala declarada**: `_should_prune` passa a logar explicitamente a escala do `estimated` (raw) e da `best_reward_so_far` (raw), e a margem `+0.15` passa a ser configurável via `prune_relative_margin` no `MCTSConfig`.
- **Coordenação pré-LLM entre threads**: antes de chamar `_try_generate_mutation`, o nó leaf é "reservado" para a estratégia via um `threading.Lock` por-nó ou um `reservation` set test-and-set sobre `(leaf, strategy_key)`, impedindo que duas threads paralelas gerem mutações rendundantes do mesmo par (nó, estratégia).
- **Prior boosting condicional do Mutador Cognitivo**: o prior boosting hardcoded só é aplicado se a memória experiencial não tiver estatística negativa para `mutador_cognitivo`; se `mean_delta <= 0` na memória, o boost é suprimido e o log declara que está sendo suprimido por desempenho histórico negativo.
- **Correção da dupla contagem de `_expansion_failure`**: o bloco `else` (Gate A/B reprovou) passa a usar `continue` explícito para evitar re-execução do bloco de falha genérico, corrigindo a inflação da taxa de falha.
- **Diversificação do conjunto de estratégias**: adicionar 3 estratégias hardcoded adicionais cobrindo eixos estruturais ortogonais (`variacao_tom`, `reestruturacao_formato`, `especificacao_contexto`) e relaxar o prompt do `__DISCOVER__` para permitir eixos além dos 5 currentes (removendo a enumeração restritiva de "EIXOS DISPONÍVEIS").

## Impact
- Affected specs: `fix-mcts-performance` (circuit breaker passa a preemptivo), `fix-score-scale-consistency` (shaped agora coerente com raw), `add-mutation-gate-composition` (eficiência afetada pela dupla contagem e diversificação)
- Affected code:
  - `src/optimizer.py` — `_check_iteration_abort`, `_run_mcts_iteration`, `_commit_iteration`, `_should_prune`, `_expand_node`, `_run_threaded_search`, inicialização do prior boosting, `_try_generate_mutation`
  - `src/signatures.py` — `calcular_delta_reward` (documentação/comentário de escala)
  - `src/domain/config.py` — novos parâmetros `prune_relative_margin`; `cognitivo_prior_mean_delta` já existe
  - `src/domain/mcts.py` — possível campo `reservation_lock` ou `reserved_strategy` no `MCTSNode`
  - `src/mutation_strategies/registry.py` — 3 novas estratégias seed; `_seed_hardcoded_strategies` expandido
  - `tests/` — testes para circuit breaker preemptivo, shaping consistente, coordenação pré-LLM, prior boosting condicional, nova contagem de falhas, novas estratégias

## ADDED Requirements

### Requirement: Circuit Breaker Preemptivo de Iteração
O sistema SHALL impor o teto de tempo de iteração (`iteration_timeout_s`) de forma preemptiva, cancelando chamadas LLM em andamento quando o teto é excedido, e não apenas registrando a violação após o fato.

#### Scenario: Teto excedido durante chamada LLM
- **WHEN** uma iteração MCTS excede `iteration_timeout_s` enquanto uma chamada LLM está em andamento
- **THEN** a chamada é abortada via `future.cancel()` (ou timeout encurtado), o `TimeoutError` é tratado como falha recuperável, e o log `[Circuit Breaker]` declara o cancelamento com o tempo decorrido real (não 3x o teto)

#### Scenario: Relógio por-thread compartilhado
- **WHEN** múltiplas threads rodam no mesmo batch
- **THEN** cada thread consulta um deadline compartilhado (`iteration_deadline = t_start + iteration_timeout_s`) antes de submeter novas chamadas LLM, recusando submissão se o deadline já passou

### Requirement: Reserva Pré-LLM de Par (Nó, Estratégia)
O sistema SHALL reservar atomicamente o par `(leaf, strategy_key)` antes de invocar `_try_generate_mutation`, impedindo que duas threads paralelas gerem mutações redundantes para o mesmo nó com a mesma estratégia.

#### Scenario: Duas threads tentam o mesmo par
- **WHEN** duas threads em paralelo selecionam o mesmo leaf e o bandit retorna a mesma estratégia
- **THEN** apenas a primeira thread adquire a reserva e chama o LLM; a segunda recebe "já reservado" e seleciona outra estratégia ou outro nó

#### Scenario: Liberação da reserva em falha
- **WHEN** a thread que reservou falha na geração (gate A/B ou post-eval reprovou)
- **THEN** a reserva é liberada, permitindo que a estratégia seja re-tentada em iteração futura (não bloqueia permanentemente)

### Requirement: Diversificação do Conjunto de Estratégias
O sistema SHALL manter um conjunto de estratégias de mutação que cubra eixos estruturais ortogonais, adicionando pelo menos 3 estratégias além das 5 atuais, e relaxar o prompt do `__DISCOVER__` para permitir eixos além da enumeração fixa atual.

#### Scenario: Novas estratégias disponíveis
- **WHEN** o `StrategyRegistry` é inicializado
- **THEN** contém pelo menos 8 estratégias hardcoded cobrindo eixos distintos: compressão, enriquecimento, reorganização, preservação, mutação cognitiva, variação de tom, reestruturação de formato, especificação de contexto

#### Scenario: Discovery não restrito a eixos fixos
- **WHEN** o `__DISCOVER__` invoca o LLM para criar nova estratégia
- **THEN** o prompt permite qualquer eixo de mutação coerente com a skill, sem enumerar restritivamente "EIXOS DISPONÍVEIS" pré-definidos

### Requirement: Prior Boosting Condicional do Mutador Cognitivo
O sistema SHALL suprimir o prior boosting hardcoded do `mutador_cognitivo` quando a memória experiencial registrar `mean_delta <= 0` para essa estratégia, e logar explicitamente o motivo da supressão.

#### Scenario: Boost aplicado normalmente
- **WHEN** a memória experiencial não tem estatística para `mutador_cognitivo` ou tem `mean_delta > 0`
- **THEN** o prior boosting hardcoded é aplicado como hoje, e o log declara `prior boosting: N virtual count, delta=0.05`

#### Scenario: Boost suprimido por desempenho negativo
- **WHEN** a memória experiencial registra `mean_delta <= 0` para `mutador_cognitivo`
- **THEN** o prior boosting hardcoded é suprimido, e o log declara `prior boosting suprimido: mean_delta histórico=−0.582 <= 0`

### Requirement: Margem de Poda Relativa Configurável
O sistema SHALL expor `prune_relative_margin` (margem da poda relativa, padrão 0.15) no `MCTSConfig`, configurável via variável de ambiente `MCTS_PRUNE_RELATIVE_MARGIN`, e o log `[Poda Relativa]` deve declarar explicitamente a escala (raw) de ambos os operandos.

#### Scenario: Poda relativa com margem customizada
- **WHEN** `MCTS_PRUNE_RELATIVE_MARGIN=0.20` está definido
- **THEN** a poda relativa compara `estimated + 0.20 < best_reward_so_far` e o log declara `Estimado ({estimated:.2f} [raw] + {margin}) < melhor recompensa ({best:.2f} [raw])`

## MODIFIED Requirements

### Requirement: Shaping de Recompensa com Escala Consistente
O método `_commit_iteration` do `Optimizer` SHALL usar `child.parent.raw_reward` (escala raw) como `parent_reward` em `calcular_delta_reward`, em vez de `child.parent.last_reward` (escala multiplied). Adicionalmente, `last_reward` passa a armazenar `raw_reward` (não `multiplied_reward`) para manter coerência ao longo do DAG. O log `[Score Chain]` deve revelar o `parent_reward` usado e sua escala.

#### Scenario: Shaped coerente com raw original
- **WHEN** um nó filho tem `raw=0.711`, `mult=0.852`, e o pai tem `raw=0.66`
- **THEN** o shaping usa `parent_reward=0.66` (raw), e `shaped = 0.6 * 0.852 + 0.4 * (0.852 - 0.66) = 0.511 + 0.077 = 0.588`, e o log declara `parent_raw=0.66` para auditoria

#### Scenario: last_reward armazena raw
- **WHEN** um nó é commitado
- **THEN** `node.last_reward = node.raw_reward` (não `multiplied_reward`), e o neto usa `parent.last_reward = raw` para shaping consistentemente

### Requirement: Contagem Singular de Falhas de Expansão
O método `_expand_node` SHALL contar cada falha de expansão exatamente uma vez por tentativa, usando `continue` explícito no bloco `else` (Gate A/B reprovou) para evitar re-execução do bloco genérico de falha subsequente.

#### Scenario: Gate A/B reprova uma vez
- **WHEN** o Gate A/B reprova uma mutação
- **THEN** `_expansion_failure[strategy_key]` é incrementado exatamente uma vez, e o bloco genérico de falha (linhas 985-995) não é executado para essa tentativa

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
