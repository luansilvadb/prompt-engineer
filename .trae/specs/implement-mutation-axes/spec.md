# Sistema de Mutação de Prompts em Quatro Eixos Especiação

## Why
O sistema atual possui apenas uma estratégia de mutação hardcoded ("Mutador Cognitivo") e um mecanismo de descoberta autônoma (`__DISCOVER__`) que inventa heurísticas livremente. Isso produz mutações não-estruturadas e sem diversidade técnica garantida — o bandit não consegue explorar eixos distintos de mutação de forma sistemática. O sistema precisa de quatro eixos de mutação tecnicamente ortogonais, cada um operando sobre uma dimensão diferente do prompt, combinados com um gate de avaliação A/B empírico que bloqueia qualquer mutação que não demonstre melhoria mensurável sobre a versão original.

## What Changes
- Implementação de quatro eixos de mutação distintos como estratégias registradas no `StrategyRegistry`:
  - **Compressão/Formalização**: reduz redundâncias, padroniza estrutura, mantém capacidade funcional
  - **Enriquecimento com exemplos**: adiciona exemplos práticos e contra-exemplos contextuais
  - **Reorganização por prioridade de falha**: reordena conteúdo com base na frequência de erros registrados no experience store
  - **Preservação seletiva de blocos eficazes**: retém blocos de raciocínio que resolveram casos ambíguos
- Gate de avaliação A/B obrigatório: antes de aprovar qualquer mutação, o sistema executa a skill mutada e a skill original contra a base de casos de feedback (experience store) e compara os scores
- Nenhuma mutação é aceita apenas com base em estrutura ou forma textual — somente após melhoria empírica mensurável
- Integração dos quatro eixos como prompts de estratégia no `_seed_hardcoded_strategies()` do registry
- **BREAKING**: mutações que falham no gate A/B são rejeitadas mesmo que estruturalmente válidas

## Impact
- Affected specs: align-mcts-dspy (o bandit agora tem 4 braços estruturados além de `__DISCOVER__`)
- Affected code: `src/mutation_strategies/registry.py` (seed das 4 estratégias), `src/optimizer.py` (gate A/B no pipeline de expansão/avaliação), `src/experience_store_sqlite.py` (query de casos de feedback), `src/signatures.py` (função de avaliação A/B)

## ADDED Requirements

### Requirement: Quatro Eixos de Mutação Estruturados
O sistema SHALL registrar quatro estratégias de mutação distintas no `StrategyRegistry`, cada operando sobre um eixo técnico ortogonal do prompt, com prompts imperativos específicos para cada eixo.

#### Scenario: Compressão e formalização
- **WHEN** o bandit seleciona a estratégia de compressão
- **THEN** o prompt enviado ao agente instrui a reduzir redundâncias, padronizar estrutura (headings, listas), e manter toda a capacidade funcional original sem perda semântica

#### Scenario: Enriquecimento com exemplos
- **WHEN** o bandit seleciona a estratégia de enriquecimento
- **THEN** o prompt enviado ao agente instrui a adicionar exemplos práticos e contra-exemplos que contextualizem casos de uso e limitações do sistema, sem remover regras existentes

#### Scenario: Reorganização por prioridade de falha
- **WHEN** o bandit seleciona a estratégia de reorganização
- **THEN** o prompt enviado ao agente inclui as frequências de erros extraídas do experience store e instrui a reposicionar as regras que resolvem os erros mais frequentes no início do texto

#### Scenario: Preservação seletiva de blocos eficazes
- **WHEN** o bandit seleciona a estratégia de preservação
- **THEN** o prompt enviado ao agente identifica blocos de raciocínio que demonstraram eficácia (delta_reward > 0 em experiências passadas) e instrui a preservá-los intactos durante a reescrita

### Requirement: Gate de Avaliação A/B Empírico
O sistema SHALL submeter toda mutação candidata a um teste A/B contra a base de casos de feedback do experience store antes de aceitá-la como válida. A mutação só é aprovada se o score médio da versão mutada for estatisticamente superior ao da versão original.

#### Scenario: Mutação aprovada por melhoria mensurável
- **WHEN** uma mutação candidata é gerada por qualquer eixo
- **THEN** o sistema avalia ambas (original e mutada) contra os N casos de feedback mais relevantes do experience store
- **AND** se o score médio da mutada > score médio da original (com margem mínima configurável), a mutação é aceita

#### Scenario: Mutação rejeitada sem melhoria
- **WHEN** o score médio da mutada não supera o da original pela margem mínima
- **THEN** a mutação é rejeitada, o nó não é expandido, e o bandit registra reward 0 para aquela estratégia naquela iteração

#### Scenario: Avaliação A/B com casos de feedback
- **WHEN** o gate A/B executa
- **THEN** utiliza os registros do experience_store (feedback + instruction + delta_reward) como casos de teste, avaliando a skill mutada e a original com o `funcao_de_recompensa`

### Requirement: Query de Casos de Feedback por Prioridade de Falha
O sistema SHALL consultar o experience store para obter a frequência de tipos de erro/feedback, ordenados por ocorrência, para alimentar a estratégia de reorganização por prioridade de falha.

#### Scenario: Frequência de erros extraída
- **WHEN** a estratégia de reorganização é selecionada
- **THEN** o sistema extrai do experience store os feedbacks mais frequentes (clusterizados por similaridade TF-IDF) e fornece ao agente a lista ordenada de erros mais comuns

#### Scenario: Erros relevantes injetados no prompt
- **WHEN** os erros são extraídos
- **THEN** os top-K feedbacks com menor delta_reward (piores resultados) são priorizados no prompt de reorganização

### Requirement: Identificação de Blocos Eficazes para Preservação
O sistema SHALL identificar blocos de raciocínio (seções de texto delimitadas) que demonstraram eficácia em experiências passadas, marcando-os para preservação durante a mutação.

#### Scenario: Blocos com delta positivo identificados
- **WHEN** a estratégia de preservação é selecionada
- **THEN** o sistema consulta o experience store por experiências com delta_reward > 0 e extrai os trechos de instruction que correlacionam com bons resultados

#### Scenario: Blocos eficazes injetados no prompt
- **WHEN** os blocos eficazes são identificados
- **THEN** são fornecidos ao agente como trechos que DEVEM ser preservados literalmente na nova versão

## MODIFIED Requirements

### Requirement: Estratégias de Mutação no Registry
O `_seed_hardcoded_strategies()` do `StrategyRegistry` SHALL registrar as quatro estratégias de eixo como estratégias hardcoded permanentes, além do "Mutador Cognitivo" já existente.

#### Scenario: Registry com 5 estratégias base
- **WHEN** o registry é inicializado
- **THEN** contém as estratégias: `mutador_cognitivo`, `compressao_formalizacao`, `enriquecimento_exemplos`, `reorganizacao_falha`, `preservacao_blocos`

### Requirement: Pipeline de Expansão com Gate A/B
O método `_expand_node` do `Optimizer` SHALL, após gerar uma candidata válida, executar o gate A/B antes de criar o nó filho. Se o gate reprovar, a estratégia é marcada como falha para aquele nó.

#### Scenario: Candidata passa no gate A/B
- **WHEN** a candidata gerada passa na validação estrutural (_is_candidate_valid)
- **AND** passa no gate A/B (score mutada > original + margem)
- **THEN** o nó filho é criado normalmente

#### Scenario: Candidata falha no gate A/B
- **WHEN** a candidata gerada passa na validação estrutural
- **BUT** falha no gate A/B
- **THEN** a estratégia é adicionada a `failed_strategies` e o ciclo tenta outra estratégia

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
