# Avaliação Pós-Mutação e Composição de Estratégias Spec

## Why
A spec `implement-mutation-axes` introduziu quatro eixos de mutação e um gate A/B, mas dois pontos fundamentais permanecem em aberto. Primeiro, o único critério de aceitação das mutações ainda é essencialmente estrutural/textual — o gate A/B atual reutiliza `funcao_de_recompensa`, a mesma função usada na simulação, sem uma etapa formal de avaliação pós-implementação que teste as alterações contra casos de teste independentes baseados em feedback coletado e verifique que o comportamento do agente foi efetivamente aprimorado. Segundo, as estratégias de mutação são aplicadas de forma isolada e exclusiva: o bandit seleciona exatamente uma estratégia por expansão de nó, sem suporte a composição. Isso impede combinar os pontos fortes específicos de cada eixo (ex.: compressão + preservação de blocos + reorganização por falha) em uma única passagem de processamento, perdendo a oportunidade de obter resultados mais eficazes.

## What Changes
- Implementação de uma etapa formal de **avaliação pós-implementação** que testa cada mutação aceita pelo gate A/B contra uma suíte de casos de teste baseados em feedback coletado (golden set / experience store), validando que o comportamento do agente foi efetivamente aprimorado — não apenas que o formato do texto foi modificado.
- A avaliação pós-implementação usa uma métrica independente da função de simulação, executando a skill mutada e a skill original contra os casos de teste e comparando o resultado comportamental (aderência às regras, ausência de defeitos, preservação de regras críticas).
- Implementação de **composição de estratégias** no pipeline de expansão: o bandit pode selecionar um conjunto ordenado de 2+ estratégias que são aplicadas sequencialmente em uma única passagem de processamento, produzindo um único nó filho cuja `mutation_strategy` é registrada como uma composição.
- Registro de estratégias compostas no `StrategyRegistry` e no `Experience` (para rastreabilidade no bandit) com uma convenção de nomes (ex.: `composite:compressao+preservacao`).
- **BREAKING**: o critério "formato do texto foi modificado conforme solicitado" deixa de ser condição suficiente para aceitação — toda mutação deve passar pela avaliação pós-implementação comportamental.

## Impact
- Affected specs: `implement-mutation-axes` (o gate A/B agora é uma camada intermediária; a avaliação pós-implementação é a camada final de aceitação), `align-mcts-dspy` (o bandit passa a selecionar conjuntos de estratégias, não apenas estratégias isoladas)
- Affected code:
  - `src/optimizer.py` — `_expand_node` (aplicação sequencial de múltiplas estratégias), nova etapa de avaliação pós-implementação, `_run_ab_gate` (papel remodelado como camada intermediária)
  - `src/mutation_strategies/bandit.py` — `select()` passa a poder retornar uma lista ordenada de estratégias (composição)
  - `src/mutation_strategies/registry.py` — registro e resolução de estratégias compostas, método de concatenação de prompts
  - `src/domain/bandit_interfaces.py` — interface `IMutationBandit` e `BanditStats` adaptadas para suportar composição
  - `src/domain/config.py` — novos parâmetros (`composition_max_strategies`, `post_eval_sample_size`)
  - `src/domain/store_interfaces.py` — `IExperienceStore` pode precisar de método para casos de teste da avaliação pós-implementação (reaproveitar `get_ab_test_cases` ou novo método)
  - `src/experience_store_sqlite.py` — persistência de estratégias compostas no campo `mutation_strategy`
  - `src/signatures.py` — possível nova funcionalidade de avaliação comportamental independente
  - `tests/` — testes para composição e avaliação pós-implementação

## ADDED Requirements

### Requirement: Avaliação Pós-Implementação Comportamental
O sistema SHALL submeter toda mutação candidata (após passar pelo gate A/B) a uma etapa formal de avaliação pós-implementação que testa a skill mutada e a skill original contra uma suíte de casos de teste baseados em feedback coletado, verificando que o comportamento do agente foi efetivamente aprimorado. A mutação só é aceita como válida se a versão mutada demonstrar melhoria comportamental mensurável sobre a versão original.

#### Scenario: Mutação aprovada por melhoria comportamental
- **WHEN** uma mutação candidata passa pelo gate A/B
- **THEN** o sistema executa a avaliação pós-implementação contra os N casos de teste da suíte de feedback
- **AND** a avaliação mede aderência às regras, ausência de defeitos e preservação de regras críticas para ambas as versões (original e mutada)
- **AND** se a mutada supera a original por margem mínima configurável em score comportamental, a mutação é aceita

#### Scenario: Mutação rejeitada sem melhoria comportamental
- **WHEN** a avaliação pós-implementação não demonstra melhoria comportamental da mutada sobre a original
- **THEN** a mutação é rejeitada, o nó filho não é criado, e a estratégia (ou composição) é marcada como falha

#### Scenario: Suíte de casos de teste baseada em feedback coletado
- **WHEN** a avaliação pós-implementação executa
- **THEN** utiliza os casos do golden set e/ou experience store (feedback + instruction + delta_reward) como casos de teste comportamentais
- **AND** cada caso é avaliado de forma independente da função de simulação usada no MCTS, utilizando o avaliador de modo B com foco em comportamento (regras críticas preservadas, defeitos ausentes)

#### Scenario: Critério estrutural insuficiente
- **WHEN** uma mutação modifica apenas o formato textual mas não passa na avaliação pós-implementação comportamental
- **THEN** a mutação é rejeitada mesmo que estruturalmente válida e mesmo que tenha passado no gate A/B

### Requirement: Composição de Estratégias de Mutação
O sistema SHALL suportar a aplicação de múltiplas estratégias de mutação em uma única passagem de processamento, combinando os eixos ortogonais (compressão, enriquecimento, reorganização, preservação) de forma sequencial e ordenada, produzindo um único nó filho cuja estratégia é registrada como uma composição.

#### Scenario: Bandit seleciona composição de estratégias
- **WHEN** o bandit decide aplicar uma composição (com probabilidade configurável)
- **THEN** seleciona um conjunto ordenado de 2 a N estratégias (limite máximo configurável) do registry
- **AND** as estratégias são aplicadas sequencialmente: a saída de uma é a entrada da próxima
- **AND** o nó filho resultante tem `mutation_strategy` registrada como `composite:estrat1+estrat2+...`

#### Scenario: Aplicação sequencial em única passagem
- **WHEN** uma composição de estratégias é aplicada
- **THEN** o sistema obtém o prompt da primeira estratégia (com injeção de dados dinâmicos), gera a mutação intermediária, e a usa como entrada para a próxima estratégia
- **AND** o resultado final é uma única instrução mutada que reflete a combinação de todos os eixos

#### Scenario: Composição submetida ao gate A/B e avaliação pós-implementação
- **WHEN** uma composição produz uma candidata válida
- **THEN** ela passa pelo gate A/B e pela avaliação pós-implementação sob as mesmas regras de estratégias isoladas
- **AND** se reprovada, a composição inteira é marcada como falha

#### Scenario: Estratégia composta rastreada no experience store
- **WHEN** uma mutação composta é aceita
- **THEN** o experience store registra `mutation_strategy` como `composite:estrat1+estrat2`
- **AND** o bandit acumula reward para a chave composta, permitindo que composições bem-sucedidas sejam exploradas

### Requirement: Configuração da Composição e Avaliação
O sistema SHALL expor parâmetros configuráveis para controlar a composição de estratégias e a avaliação pós-implementação.

#### Scenario: Parâmetros de composição
- **WHEN** o MCTSConfig é carregado
- **THEN** contém `composition_max_strategies` (número máximo de estratégias por composição, padrão 3) e `composition_probability` (probabilidade de selecionar composição ao invés de estratégia isolada, padrão 0.3)
- **AND** ambos são configuráveis via variáveis de ambiente

#### Scenario: Parâmetros de avaliação pós-implementação
- **WHEN** o MCTSConfig é carregado
- **THEN** contém `post_eval_margin_min` (margem mínima de melhoria comportamental para aceitação, padrão 0.05) e `post_eval_sample_size` (número de casos de teste, padrão 5)
- **AND** ambos são configuráveis via variáveis de ambiente

## MODIFIED Requirements

### Requirement: Pipeline de Expansão com Gate A/B e Avaliação Pós-Implementação
O método `_expand_node` do `Optimizer` SHALL, após gerar uma candidata válida, executar o gate A/B (camada intermediária) e, se aprovada, executar a avaliação pós-implementação (camada final). Se qualquer camada reprovar, a estratégia (ou composição) é marcada como falha para aquele nó.

#### Scenario: Candidata passa em todas as camadas
- **WHEN** a candidata gerada passa na validação estrutural (_is_candidate_valid)
- **AND** passa no gate A/B (score mutada > original + margem)
- **AND** passa na avaliação pós-implementação (melhoria comportamental demonstrada)
- **THEN** o nó filho é criado normalmente

#### Scenario: Candidata falha na avaliação pós-implementação
- **WHEN** a candidata gerada passa na validação estrutural e no gate A/B
- **BUT** falha na avaliação pós-implementação
- **THEN** a estratégia (ou composição) é adicionada a `failed_strategies` e o ciclo tenta outra estratégia ou composição

### Requirement: Seleção do Bandit com Suporte a Composição
O método `select()` de `IMutationBandit` SHALL poder retornar uma única estratégia isolada ou uma lista ordenada de estratégias (composição), com probabilidade controlada por `composition_probability`.

#### Scenario: Seleção de estratégia isolada
- **WHEN** o bandit decide não compor (com probabilidade 1 - composition_probability)
- **THEN** retorna uma única estratégia como faz atualmente

#### Scenario: Seleção de composição
- **WHEN** o bandit decide compor (com probabilidade composition_probability)
- **THEN** retorna uma lista ordenada de 2 a composition_max_strategies estratégias distintas
- **AND** a chave composta é registrada no bandit para rastreamento de reward

### Requirement: Registro de Estratégias Compostas no Registry
O `StrategyRegistry` SHALL suportar o registro e resolução de estratégias compostas, permitindo que composições sejam persistidas e rastreadas.

#### Scenario: Chave composta registrada
- **WHEN** uma composição é gerada e aceita
- **THEN** o registry registra a chave `composite:estrat1+estrat2` com nome legível e prompt concatenado
- **AND** composições subsequentes com as mesmas estratégias reaproveitam a mesma chave

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
