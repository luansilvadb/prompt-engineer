# Correção de Performance e Duplicação de Logs no MCTS Spec

## Why
O pipeline MCTS RL customizado apresenta três anomalias críticas: (1) lentidão excessiva com aparente travamento após as primeiras iterações, (2) duplicação da mensagem de expansão "Expandindo nó (Tentativa 1/3)" que aparece 3 vezes consecutivas sem progressão, e (3) estagnação antes de concluir as 75 iterações programadas. A causa raiz está na combinação de um modelo de threading que submete todas as iterações simultaneamente, ausência de timeouts em chamadas LLM, falha na progressão de tentativas de expansão por re-seleção cíclica da mesma estratégia, e virtual count zero para o Mutador Cognitivo que impede sua seleção pelo bandit.

## What Changes
- Correção do loop de expansão para garantir progressão real de tentativas (1/3 → 2/3 → 3/3) e evitar re-seleção da mesma estratégia falha
- Adição de timeout (60s) em chamadas LLM de descoberta (`__DISCOVER__`) e geração de mutação para evitar hangs
- Ajuste do `cognitivo_prior_count` padrão de 1 para 4 e aplicação de `max(1, int(count * 0.5))` no `load_priors` para garantir virtual count mínimo de 1
- Refatoração do `_run_threaded_search` para submissão em batches de `num_threads` iterações por vez, evitando saturação do pool
- Adição de logs de progressão detalhados com timestamp e latência por nó em cada iteração MCTS
- Proteção contra loop infinito em `_try_fallback_strategy` com limite de tentativas por `failed_strategies`

## Impact
- Affected specs: fix-mcts-performance (nova)
- Affected code: `src/optimizer.py`, `src/mutation_strategies/bandit.py`, `src/domain/config.py`

## ADDED Requirements

### Requirement: Progressão Real de Tentativas de Expansão
O sistema SHALL garantir que o loop de tentativas em `_expand_node` incremente o contador de tentativas corretamente e nunca re-selecione uma estratégia que já falhou na mesma rodada de expansão.

#### Scenario: Três tentativas com estratégias diferentes
- **WHEN** uma estratégia falha na geração de candidata válida
- **THEN** a próxima tentativa usa uma estratégia diferente (não presente em `failed_strategies`) e o log mostra "Tentativa 2/3"

#### Scenario: Estratégia falha não é re-selecionada
- **WHEN** `_try_fallback_strategy` é chamado com `failed_strategies` contendo a estratégia atual
- **THEN** a mesma estratégia NÃO é retornada; se nenhuma estratégia alternativa existir, retorna `None` e o nó pai é retornado sem expansão

### Requirement: Timeout em Chamadas LLM
O sistema SHALL configurar timeout de 60 segundos em todas as chamadas LLM do pipeline MCTS (`strategy_discoverer`, `agent_cognitivo`, `agent`, `avaliador_modo_b`) para evitar travamento indefinido.

#### Scenario: LLM não responde em 60s
- **WHEN** uma chamada LLM excede 60 segundos sem resposta
- **THEN** a chamada é abortada com `TimeoutError` e o erro é tratado como falha recuperável (tenta próxima estratégia ou retorna fallback)

#### Scenario: Timeout configurável
- **WHEN** a variável de ambiente `MCTS_LLM_TIMEOUT` está definida
- **THEN** o timeout usa o valor configurado em segundos

### Requirement: Virtual Count Mínimo para Prior Boosting
O sistema SHALL garantir que o `load_priors` do `MutationBandit` aplique um virtual count mínimo de 1 quando `int(count * 0.5)` resultar em 0, assegurando que estratégias com prior baixo ainda recebam boost inicial.

#### Scenario: Prior count=1 gera virtual count=1
- **WHEN** `load_priors` recebe `count=1` para uma estratégia
- **THEN** `virtual_count = max(1, int(1 * 0.5)) = 1`, garantindo que a estratégia tenha ao menos 1 pull virtual

#### Scenario: Prior count=10 gera virtual count=5
- **WHEN** `load_priors` recebe `count=10` para uma estratégia
- **THEN** `virtual_count = max(1, min(int(10 * 0.5), 10)) = 5`

### Requirement: Threading em Batches Controlados
O sistema SHALL submeter iterações MCTS ao `ThreadPoolExecutor` em batches de tamanho `num_threads`, aguardando a conclusão de cada batch antes de submeter o próximo, em vez de submeter todas as `max_iterations` de uma vez.

#### Scenario: 75 iterações com num_threads=4
- **WHEN** `max_iterations=75` e `num_threads=4`
- **THEN** as iterações são submetidas em 19 batches (18 batches de 4 + 1 batch de 3), e cada batch aguarda a conclusão completa antes do próximo

#### Scenario: Cancelamento durante batch
- **WHEN** o usuário cancela a otimização durante um batch
- **THEN** o executor é shutdown e as iterações restantes são canceladas

### Requirement: Logs de Progressão com Timestamp e Latência
O sistema SHALL emitir logs de progressão a cada iteração MCTS contendo: timestamp ISO-8601, número da iteração, tempo total da iteração em ms, estratégia usada, recompensa obtida, e profundidade do nó expandido.

#### Scenario: Log de progressão emitido
- **WHEN** uma iteração MCTS completa (com sucesso ou falha)
- **THEN** um log no formato `[ITER 12/75] 2026-07-23T14:30:05 | 2.34s | strat=mutador_cognitivo | reward=0.657 | depth=3` é emitido

## MODIFIED Requirements

### Requirement: Loop de Expansão com Fallback Determinístico
O método `_expand_node` do `Optimizer` SHALL ser modificado para:
1. Mover o log "Expandindo nó (Tentativa X/3)" para dentro do bloco que só executa quando uma estratégia válida é selecionada
2. Garantir que `_try_fallback_strategy` receba o `failed_strategies` atualizado ANTES de selecionar nova estratégia
3. Emitir log de warning quando `_try_fallback_strategy` retornar a mesma estratégia que já falhou
4. Limitar `_try_fallback_strategy` a 5 tentativas de seleção de estratégia não-falha antes de retornar `None`

#### Scenario: Três falhas consecutivas com estratégias diferentes
- **WHEN** 3 estratégias diferentes falham na geração
- **THEN** o log mostra Tentativa 1/3, 2/3, 3/3 com estratégias distintas, e após a 3ª falha o nó pai é retornado

### Requirement: Configuração de Prior do Mutador Cognitivo
O valor padrão de `cognitivo_prior_count` em `load_mcts_config()` SHALL ser alterado de 1 para 4, garantindo que o Mutador Cognitivo receba virtual count mínimo de 2 no bandit.

#### Scenario: Config padrão carregada
- **WHEN** `load_mcts_config()` é chamada sem variáveis de ambiente
- **THEN** `cognitivo_prior_count=4` (era 1)

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
