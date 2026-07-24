# Controle de Custo e Tempo por Iteração Spec

## Why
O log de execução de ~48 minutos mostra uma explosão de custo operacional: apenas 10 de 75 iterações completadas, com pico de 1822s (30+ min) em uma única iteração que terminou com reward=0.000 por rejeição total das candidatas pelos gates. Estratégias compostas de 3 etapas acumulam timeouts de 60s × retries × gate A/B + Post-Eval, gerando até 90 chamadas LLM por iteração sem garantia de retorno. Sem teto de custo por iteração, o sistema gasta desproporcionalmente em iterações infrutíferas, e o usuário cancela antes da conclusão.

## What Changes
- **Orçamento por iteração (circuit breaker)**: Cada iteração MCTS recebe um teto máximo de segundos (`iteration_timeout_s`) e de chamadas LLM (`iteration_llm_call_limit`). Ao exceder qualquer um, a iteração é abortada e prossegue-se para a próxima.
- **Abordagem gradativa de estratégias**: Em vez de tentar composição de 3 estratégias de cara, o sistema tenta primeiro uma estratégia simples. Se ela falhar no gate, escala para composição de 2; se falhar de novo, escala para composição de 3. Isso evita pagar o custo máximo sem evidência de que vale a pena.
- **Métrica de custo-benefício por estratégia/estratégia composta**: O bandit passa a rastrear `total_llm_calls` e `total_tokens_estimated` por chave de estratégia, expondo o custo médio por aprovação no log final (`custo_por_aprovacao = total_llm_calls / expansoes_bem_sucedidas`). Estratégias com custo muito acima da mediana recebem penalidade no score UCB.
- **Persistência do melhor nó a cada aprovação**: Após cada `_commit_iteration` que produz um nó com score superior ao `best_reward_so_far`, o sistema grava a instrução em arquivo de checkpoint (`outputs/strategies/checkpoint_{job_id}.json`), garantindo que progresso não seja perdido em caso de cancelamento.
- **Investigação e correção da "Penalidade por Densidade" fixa em 0.50**: O `_apply_density_multiplier` atual compara `len(parent) == len(child)` e retorna sem penalidade nesse caso, mas quando os tamanhos diferem, o default `density_threshold=1.0` combinado com `density_multiplier_min=0.5` faz com que qualquer filho ≥2x maior que o pai receba penalidade exata de 0.50. O log deve expor a razão `child_len/parent_len` que gerou o multiplicador para permitir auditoria.
- **Redução do timeout de composição**: Para estratégias compostas, o timeout por etapa é reduzido de 60s para 45s, já que a latência acumulada de 3 etapas com timeout cheio é proibitiva.

## Impact
- Affected specs: `fix-mcts-performance` (complementa controle de recursos), `add-mutation-gate-composition` (ajusta timeout e ordem de tentativas de composição), `fix-output-quality-guards` (checkpoint complementa guarda anti-regressão)
- Affected code:
  - `src/optimizer.py` — `_expand_node` (abordagem gradativa de composição), `_run_single_iteration` (circuit breaker de iteração), `_commit_iteration` (persistência de checkpoint), `_apply_density_multiplier` (log da razão de tamanhos), `_try_generate_mutation` (timeout reduzido para composição)
  - `src/domain/config.py` — novos parâmetros: `iteration_timeout_s`, `iteration_llm_call_limit`, `composite_timeout_s`
  - `src/mutation_strategies/bandit.py` — rastreamento de `total_llm_calls` e `estimated_tokens` por chave, cálculo de custo-por-aprovação, penalidade UCB baseada em custo
  - `src/domain/bandit_interfaces.py` — extensão de `BanditStats` com campos de custo

## ADDED Requirements

### Requirement: Circuit Breaker por Iteração
O sistema SHALL abortar uma iteração MCTS quando ela exceder `iteration_timeout_s` segundos ou `iteration_llm_call_limit` chamadas LLM, passando para a próxima iteração sem interromper a otimização inteira.

#### Scenario: Iteração excede teto de tempo
- **WHEN** `_run_single_iteration` ultrapassa `iteration_timeout_s` segundos desde seu início
- **THEN** a iteração é abortada com log: "[Circuit Breaker] Iteração excedeu teto de {iteration_timeout_s}s. Abortando."
- **AND** o contador de iterações avança normalmente (não conta como plateau)
- **AND** `consecutive_zeros` NÃO é incrementado (abort por tempo não é evidência de estagnação)

#### Scenario: Iteração excede teto de chamadas LLM
- **WHEN** `_llm_call_count` da iteração atual atinge `iteration_llm_call_limit`
- **THEN** a iteração é abortada com log: "[Circuit Breaker] Iteração excedeu teto de {iteration_llm_call_limit} chamadas LLM. Abortando."
- **AND** procede como no cenário de timeout

#### Scenario: Iteração dentro do orçamento
- **WHEN** uma iteração completa dentro dos limites de tempo e chamadas
- **THEN** comportamento normal (sem abort)

### Requirement: Abordagem Gradativa de Estratégias de Mutação
O sistema SHALL tentar estratégias em ordem crescente de complexidade: primeiro estratégia simples (isolada), depois composição de 2, depois composição de 3. A progressão só ocorre se a tentativa anterior foi rejeitada pelo gate.

#### Scenario: Estratégia simples aprovada de primeira
- **WHEN** `tentativa == 0` e o bandit seleciona uma estratégia isolada
- **THEN** a mutação é gerada com 1 chamada LLM (não composta)
- **AND** se aprovada no gate A/B e Post-Eval, o nó é criado sem tentar composição

#### Scenario: Estratégia simples rejeitada → composição de 2
- **WHEN** `tentativa == 0` com estratégia isolada é rejeitada pelo gate
- **THEN** na `tentativa == 1`, o sistema força seleção de composição com exatamente 2 estratégias (não 3)
- **AND** `composition_max_strategies` para esta tentativa é limitado a 2

#### Scenario: Composição de 2 rejeitada → composição de 3
- **WHEN** `tentativa == 1` com composição de 2 é rejeitada
- **THEN** na `tentativa == 2`, o sistema tenta composição de 3 (valor normal de `composition_max_strategies`)
- **AND** se todas falharem, retorna o nó pai sem expansão

#### Scenario: Bandit naturalmente seleciona composição na primeira tentativa
- **WHEN** `tentativa == 0` e o bandit já seleciona uma composição (probabilidade natural)
- **THEN** a composição é aplicada normalmente (não reduzida), pois o bandit decidiu que vale a pena
- **AND** a abordagem gradativa NÃO força redução de estratégias que o bandit escolheu compor

### Requirement: Rastreamento de Custo por Estratégia no Bandit
O sistema SHALL rastrear métricas de custo (`total_llm_calls`, `estimated_tokens`) por chave de estratégia no bandit e expor o custo médio por aprovação no log final, aplicando penalidade no score UCB para estratégias com custo acima da mediana.

#### Scenario: Custo acumulado por estratégia
- **WHEN** uma expansão é bem-sucedida com estratégia X que usou N chamadas LLM
- **THEN** `bandit.total_llm_calls[X] += N` e `bandit.estimated_tokens[X] += N * 2000`
- **AND** `bandit.successful_expansions[X] += 1` (já existente)

#### Scenario: Log de custo-por-aprovação no final
- **WHEN** `_log_final_stats` é chamado
- **THEN** para cada estratégia com expansões bem-sucedidas > 0, loga: `"    {desc}: {successes} aprovações, {total_calls} chamadas LLM, custo/aprov={calls_per_approval:.1f}"`

#### Scenario: Penalidade UCB por custo excessivo
- **WHEN** o bandit calcula UCB para seleção de estratégia
- **THEN** estratégias com `custo_por_aprovacao > mediana * 1.5` recebem penalidade de -0.15 no score UCB
- **AND** a penalidade é proporcional: `penalty = min(0.30, (custo / mediana - 1.0) * 0.15)`

### Requirement: Checkpoint do Melhor Nó a Cada Aprovação
O sistema SHALL persistir a instrução do melhor nó em arquivo de checkpoint sempre que uma nova melhor recompensa for atingida e o nó for aprovado pelos gates.

#### Scenario: Novo melhor nó aprovado
- **WHEN** `_commit_iteration` é chamada com um nó cujo `reward > best_reward_so_far` (antes do update)
- **THEN** o sistema grava `outputs/strategies/checkpoint_{job_id}.json` com:
  - `instruction`: texto da instrução
  - `score`: reward do nó
  - `strategy`: chave da estratégia
  - `depth`: profundidade do nó
  - `timestamp`: ISO-8601
  - `iteration`: iteração atual
- **AND** emite log: "[Checkpoint] Melhor nó salvo: score={reward:.3f}, strategy={strategy}"

#### Scenario: Otimização cancelada com checkpoint existente
- **WHEN** a otimização é cancelada e `_format_best_node` é chamado
- **THEN** se existe checkpoint com score > score do melhor nó em memória, o sistema emite log avisando que o checkpoint pode conter resultado superior

#### Scenario: Nenhum nó supera o anterior
- **WHEN** nenhuma iteração produz nó com score > best_reward_so_far
- **THEN** nenhum checkpoint é escrito (sem I/O desnecessário)

### Requirement: Transparência no Multiplicador de Densidade
O sistema SHALL logar a razão `child_len/parent_len` que gerou o multiplicador de densidade, permitindo auditoria de quando a penalidade é realmente variável vs. quando está fixa no piso de 0.50.

#### Scenario: Multiplicador de densidade aplicado
- **WHEN** `_apply_density_multiplier` calcula um multiplicador diferente de 1.0
- **THEN** o log inclui: `"    [Penalidade por Densidade] child_len={cl}/{pl} parent | raw_mult={raw:.3f} → clamped={final:.3f} | Fator: {final:.2f}"`
- **AND** isso permite distinguir entre "penalidade variável (ex.: 0.73)" e "penalidade no piso (0.50 porque child ≥ 2x parent)"

#### Scenario: Multiplicador no piso repetidamente
- **WHEN** mais de 80% das penalidades de densidade nas últimas 10 iterações foram exatamente `density_multiplier_min`
- **THEN** o sistema emite WARNING: "[Density Audit] {pct}% das penalidades de densidade estão no piso ({density_multiplier_min}). Considere ajustar density_threshold ou o piso."

### Requirement: Timeout Reduzido para Etapas de Composição
O sistema SHALL usar um timeout menor (`composite_timeout_s`, padrão 45s) para chamadas LLM que fazem parte de uma composição multi-etapa, reduzindo o custo máximo de uma composição que falha por timeout.

#### Scenario: Etapa de composição com timeout reduzido
- **WHEN** `_try_generate_mutation` é chamada como parte de uma composição (não como estratégia isolada)
- **THEN** o timeout usado é `composite_timeout_s` (padrão 45s) em vez de `llm_timeout` (60s)
- **AND** o parâmetro `composite_timeout_s` é configurável via `MCTS_COMPOSITE_TIMEOUT_S`

#### Scenario: Estratégia isolada mantém timeout normal
- **WHEN** `_try_generate_mutation` é chamada para estratégia isolada
- **THEN** o timeout usado é `llm_timeout` (60s), sem alteração

## MODIFIED Requirements

### Requirement: Loop de Expansão com Progressão Gradativa (modifica requisito de `fix-mcts-performance`)
O método `_expand_node` do `Optimizer` SHALL aplicar a abordagem gradativa: tentativa 0 usa o que o bandit retornar naturalmente; se rejeitada e era estratégia isolada, tentativa 1 força composição de 2; se rejeitada, tentativa 2 força composição de 3.

#### Scenario: Progressão gradativa completa
- **WHEN** as 3 tentativas seguem o padrão: isolada → composta-2 → composta-3
- **THEN** o log mostra: "Tentativa 1/3: estratégia isolada", "Tentativa 2/3: composição (2 eixos)", "Tentativa 3/3: composição (3 eixos)"

### Requirement: Configuração de Timeout por Contexto (modifica requisito de `fix-mcts-performance`)
O `MCTSConfig` SHALL incluir `iteration_timeout_s` (padrão 300, via `MCTS_ITERATION_TIMEOUT_S`), `iteration_llm_call_limit` (padrão 50, via `MCTS_ITERATION_LLM_CALL_LIMIT`), e `composite_timeout_s` (padrão 45, via `MCTS_COMPOSITE_TIMEOUT_S`).

#### Scenario: Config padrão carregada
- **WHEN** `load_mcts_config()` é chamada sem variáveis de ambiente
- **THEN** `iteration_timeout_s=300`, `iteration_llm_call_limit=50`, `composite_timeout_s=45`

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
