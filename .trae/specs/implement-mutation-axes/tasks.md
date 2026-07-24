# Tasks

- [x] Task 1: Registrar os quatro eixos de mutação no StrategyRegistry
  - [x] SubTask 1.1: Adicionar prompts imperativos para `compressao_formalizacao`, `enriquecimento_exemplos`, `reorganizacao_falha`, `preservacao_blocos` no `_seed_hardcoded_strategies()` de `src/mutation_strategies/registry.py`
  - [x] SubTask 1.2: Garantir que cada estratégia tenha nome legível e prompt específico descrevendo o eixo técnico

- [x] Task 2: Implementar gateway de casos de feedback no Experience Store
  - [x] SubTask 2.1: Adicionar método `get_feedback_frequency(top_k)` em `SqliteExperienceStore` que retorna os feedbacks mais frequentes/impactantes ordenados por menor delta_reward
  - [x] SubTask 2.2: Adicionar método `get_effective_blocks(top_k)` que retorna trechos de instruction de experiências com delta_reward > 0, agrupados por similaridade
  - [x] SubTask 2.3: Adicionar método `get_ab_test_cases(top_k)` que retorna os N casos de feedback mais relevantes (por skill_hash) para usar como base de teste A/B

- [x] Task 3: Implementar o Gate de Avaliação A/B no Optimizer
  - [x] SubTask 3.1: Criar método `_run_ab_gate(instruction_original, instruction_mutada, test_cases)` que avalia ambas versões contra os casos de feedback e retorna (approved, scores_original, scores_mutada)
  - [x] SubTask 3.2: Definir margem mínima configurável (`ab_margin_min`) no MCTSConfig
  - [x] SubTask 3.3: Integrar o gate A/B no `_expand_node` após `_is_candidate_valid` — se reprovado, marcar estratégia como failed

- [x] Task 4: Alimentar estratégias com dados dinâmicos do experience store
  - [x] SubTask 4.1: Modificar `_pick_strategy` ou `_expand_node` para injetar frequência de erros no prompt da estratégia de reorganização
  - [x] SubTask 4.2: Modificar `_expand_node` para injetar blocos eficazes no prompt da estratégia de preservação
  - [x] SubTask 4.3: Garantir que as estratégias de compressão e enriquecimento usem prompts estáticos (sem dados dinâmicos)

- [x] Task 5: Testes de validação
  - [x] SubTask 5.1: Teste unitário verificando que o registry contém as 5 estratégias após inicialização
  - [x] SubTask 5.2: Teste unitário do gate A/B aprovando mutada superior e rejeitando mutada inferior
  - [x] SubTask 5.3: Teste unitário dos métodos `get_feedback_frequency`, `get_effective_blocks`, `get_ab_test_cases` no experience store

# Task Dependencies
- [Task 3] depends on [Task 2] (gate A/B usa os casos de feedback)
- [Task 4] depends on [Task 2] (injeção de dados dinâmicos usa métodos do store)
- [Task 5] depends on [Task 1], [Task 2], [Task 3]
