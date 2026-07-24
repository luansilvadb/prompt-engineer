# Tasks

- [x] Task 1: Modernizar Signatures DSPY com type hints
  - [x] SubTask 1.1: Atualizar `StrategyDiscovererSignature` com type hints (`str`, `float`, etc.) nos campos
  - [x] SubTask 1.2: Atualizar `SelfReflectiveAgentSignature` com type hints
  - [x] SubTask 1.3: Atualizar `MutadorCognitivoAgentSignature` com type hints
  - [x] SubTask 1.4: Atualizar `AvaliadorDeSkillSignature` com type hints
  - [x] SubTask 1.5: Atualizar `AvaliadorModoBSignature` com type hints
  - [x] SubTask 1.6: Verificar que adaptadores (`DSPyStrategyDiscoverer`, `DSPySelfReflectiveAgent`, `DSPyMutadorCognitivoAgent`, `DSPyAvaliadorModoB`) continuam funcionais

- [x] Task 2: Criar métrica DSPY compilável e encapsular Juiz como dspy.Module
  - [x] SubTask 2.1: Criar `JudgeModule(dspy.Module)` encapsulando o AvaliadorModoB com `forward()`
  - [x] SubTask 2.2: Criar `create_dspy_metric()` que retorna função compatível com `dspy.Metric` usando a função de recompensa composicional
  - [x] SubTask 2.3: Atualizar `teleprompter.py` para usar `create_dspy_metric()` e `JudgeModule`
  - [x] SubTask 2.4: Atualizar `dspy_impl.py` `load_avaliador()` para usar `JudgeModule.load()`

- [x] Task 3: Refatorar políticas de seleção MCTS como Strategy Pattern plugável
  - [x] SubTask 3.1: Criar interface `ISelectionPolicy` com método `select(node, config) -> MCTSNode`
  - [x] SubTask 3.2: Implementar `PUCTPolicy`, `UCB1Policy`, `UCB1TunedPolicy`
  - [x] SubTask 3.3: Migrar lógica de `best_child_*` de `MCTSNode` para as políticas
  - [x] SubTask 3.4: Atualizar `Optimizer.selection()` para usar política injetada

- [x] Task 4: Implementar Knowledge-Bias UCT + limites de profundidade e sufficiency threshold
  - [x] SubTask 4.1: Adicionar `max_depth` e `sufficiency_threshold` ao `MCTSConfig`
  - [x] SubTask 4.2: Adicionar `knowledge_bias_lambda` ao `MCTSConfig` para blend prior/Q-value
  - [x] SubTask 4.3: Implementar verificação de `max_depth` em `Optimizer.selection()` e `_expand_node()`
  - [x] SubTask 4.4: Implementar verificação de `sufficiency_threshold` em `_run_mcts_iteration()`
  - [x] SubTask 4.5: Integrar `knowledge_bias_lambda` no cálculo de score das políticas de seleção

- [x] Task 5: Adicionar validações de qualidade (recompensa, expansão, retropropagação)
  - [x] SubTask 5.1: Adicionar validação de intervalo [0,1] na função de recompensa com clamping e warning
  - [x] SubTask 5.2: Adicionar contadores de sucesso/falha de expansão por estratégia no Optimizer
  - [x] SubTask 5.3: Adicionar validação de reward no `backpropagation` com clamping e alerta
  - [x] SubTask 5.4: Emitir métrica de eficiência de expansão via `emit_cost`
  - [x] SubTask 5.5: Emitir estatísticas de convergência (variância Q-value na raiz) ao final da otimização

- [x] Task 6: Implementar rastreamento de métricas DSPY e unificar configuração
  - [x] SubTask 6.1: Adicionar latência de chamada LLM ao evento de custo (`CostEventPayload`)
  - [x] SubTask 6.2: Registrar taxa de sucesso de compilação do teleprompter
  - [x] SubTask 6.3: Criar `AlignConfig` unificando `MCTSConfig` + parâmetros DSPY
  - [x] SubTask 6.4: Atualizar `load_mcts_config()` para `load_align_config()` com variáveis de ambiente DSPY

- [x] Task 7: Criar documentação do alinhamento
  - [x] SubTask 7.1: Documentar justificativas baseadas nas melhores práticas MCTS (survey Swiechowski et al.)
  - [x] SubTask 7.2: Documentar justificativas baseadas nas melhores práticas DSPY (signatures/modules/optimizers)
  - [x] SubTask 7.3: Criar guia de manutenção para sessões de pairing futuras

- [x] Task 8: Executar e validar testes integrados
  - [x] SubTask 8.1: Executar `test_mcts.py` e verificar passagem
  - [x] SubTask 8.2: Executar `test_dspy_signatures.py` e verificar passagem
  - [x] SubTask 8.3: Executar `test_optimizer.py` e `test_optimizer_integration.py` e verificar passagem
  - [x] SubTask 8.4: Executar `test_teleprompter.py` e verificar passagem
  - [x] SubTask 8.5: Verificar métricas de desempenho comparativas (taxa de sucesso MCTS, redução de erros DSPY)

# Task Dependencies
- Task 2 depende de Task 1 (Signatures modernizadas são necessárias para o JudgeModule)
- Task 3 depende de Task 1 (políticas usam MCTSNode existente)
- Task 4 depende de Task 3 (Knowledge-Bias integra com políticas de seleção plugáveis)
- Task 5 depende de Task 1, Task 2, Task 3, Task 4 (validações cobrem todos os componentes)
- Task 6 pode ser paralelizada com Task 3 e Task 4
- Task 7 pode ser paralelizada com Tasks 1-6
- Task 8 depende de Tasks 1-6
