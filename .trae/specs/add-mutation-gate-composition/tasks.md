# Tasks

- [x] Task 1: Implementar avaliação pós-implementação comportamental no Optimizer
  - [x] SubTask 1.1: Criar método `_run_post_eval(instruction_original, instruction_mutada, test_cases)` em `src/optimizer.py` que avalia ambas versões contra a suíte de casos de teste (golden set + experience store) usando o avaliador de modo B com foco em comportamento (regras críticas preservadas, defeitos ausentes), retornando (approved, score_original, score_mutada)
  - [x] SubTask 1.2: Garantir que a avaliação pós-implementação seja independente da função de simulação MCTS, usando diretamente o `avaliador_modo_b` com score comportamental composto (manteve_regras_criticas, defeitos_encontrados, feedback)
  - [x] SubTask 1.3: Integrar `_run_post_eval` no `_expand_node` logo após `_run_ab_gate` — se reprovado, marcar estratégia como failed e continuar o ciclo

- [x] Task 2: Configurar parâmetros de avaliação pós-implementação e composição
  - [x] SubTask 2.1: Adicionar `post_eval_margin_min` (padrão 0.05) e `post_eval_sample_size` (padrão 5) no `MCTSConfig` em `src/domain/config.py`, com validação de bounds e leitura via variáveis de ambiente `MCTS_POST_EVAL_MARGIN_MIN` e `MCTS_POST_EVAL_SAMPLE_SIZE`
  - [x] SubTask 2.2: Adicionar `composition_max_strategies` (padrão 3) e `composition_probability` (padrão 0.3) no `MCTSConfig`, com validação (composition_max_strategies >= 2, 0.0 <= composition_probability <= 1.0) e leitura via `MCTS_COMPOSITION_MAX_STRATEGIES` e `MCTS_COMPOSITION_PROBABILITY`

- [x] Task 3: Implementar composição de estratégias no bandit
  - [x] SubTask 3.1: Modificar `IMutationBandit.select()` em `src/domain/bandit_interfaces.py` para poder retornar `str` (estratégia isolada) ou `list[str]` (composição ordenada)
  - [x] SubTask 3.2: Modificar `MutationBandit.select()` em `src/mutation_strategies/bandit.py` para, com probabilidade `composition_probability`, selecionar 2 a `composition_max_strategies` estratégias distintas e retorná-las como lista ordenada
  - [x] SubTask 3.3: Adicionar método para gerar chave composta (`composite:estrat1+estrat2`) e registrá-la nos `_counts`/`_rewards` do bandit para rastreamento de reward
  - [x] SubTask 3.4: Adaptar `update()` e `get_stats()` para suportar chaves compostas

- [x] Task 4: Implementar aplicação sequencial de composição no _expand_node
  - [x] SubTask 4.1: Modificar `_pick_strategy` em `src/optimizer.py` para retornar `str | list[str]` conforme a saída do bandit
  - [x] SubTask 4.2: Modificar `_expand_node` para, quando o bandit retornar uma lista, aplicar as estratégias sequencialmente: a saída da estratégia i é a entrada da estratégia i+1, produzindo uma única candidata final
  - [x] SubTask 4.3: Concatenar os prompts das estratégias compostas (com injeção de dados dinâmicos de `_inject_dynamic_data` para cada uma) ao gerar a mutação
  - [x] SubTask 4.4: Registrar `mutation_strategy` do nó filho como `composite:estrat1+estrat2+...` e garantir rastreabilidade no experience store

- [x] Task 5: Suportar estratégias compostas no StrategyRegistry
  - [x] SubTask 5.1: Adicionar método `build_composite_prompt(strategy_keys: list[str])` em `src/mutation_strategies/registry.py` que concatena prompts das estratégias componentes e constrói nome legível
  - [x] SubTask 5.2: Garantir que `add_strategy` e `get_prompt` funcionem com chaves compostas (formato `composite:...`)
  - [x] SubTask 5.3: Persistir estratégias compostas bem-sucedidas no registry para reaproveitamento

- [x] Task 6: Testes de validação
  - [x] SubTask 6.1: Teste unitário da avaliação pós-implementação aprovando mutada com melhoria comportamental e rejeitando mutada sem melhoria (usando mocks do avaliador_modo_b)
  - [x] SubTask 6.2: Teste unitário do bandit retornando composição com probabilidade configurável e estratégias distintas
  - [x] SubTask 6.3: Teste unitário do `_expand_node` aplicando composição sequencial e registrando `mutation_strategy` como `composite:...`
  - [x] SubTask 6.4: Teste unitário de mutação aprovada no gate A/B mas rejeitada na avaliação pós-implementação (nó filho não é criado)
  - [x] SubTask 6.5: Teste unitário validando que `MCTSConfig` rejeita valores inválidos para os novos parâmetros
  - [x] SubTask 6.6: Teste unitário do `build_composite_prompt` no registry gerando prompt concatenado correto

# Task Dependencies
- [Task 1] depends on [Task 2] (usa post_eval_margin_min e post_eval_sample_size)
- [Task 3] depends on [Task 2] (usa composition_probability e composition_max_strategies)
- [Task 4] depends on [Task 3] (usa saída do bandit em lista) e [Task 5] (usa build_composite_prompt)
- [Task 6] depends on [Task 1], [Task 3], [Task 4], [Task 5]
