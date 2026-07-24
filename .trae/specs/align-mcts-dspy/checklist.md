# Checklist de Verificação

## Signatures DSPY Modernizadas
- [x] `StrategyDiscovererSignature` usa type hints Python (`str`, `float`) nos campos
- [x] `SelfReflectiveAgentSignature` usa type hints Python nos campos
- [x] `MutadorCognitivoAgentSignature` usa type hints Python nos campos
- [x] `AvaliadorDeSkillSignature` usa type hints Python nos campos
- [x] `AvaliadorModoBSignature` usa type hints Python nos campos
- [x] Adaptadores existentes funcionam sem alteração de interface pública

## Métrica DSPY Compilável e JudgeModule
- [x] `JudgeModule` herda de `dspy.Module` com método `forward()`
- [x] `create_dspy_metric()` retorna `(example, pred, trace=None) -> float | bool`
- [x] Métrica popula `pred.feedback` quando `trace` é não-nulo (compatível com GEPA)
- [x] `teleprompter.py` usa `create_dspy_metric()` e `JudgeModule`
- [x] `load_avaliador()` usa `JudgeModule.load()` padronizado

## Políticas de Seleção MCTS Plugáveis
- [x] Interface `ISelectionPolicy` definida com método `select(node, config)`
- [x] `PUCTPolicy` implementada com lógica extraída de `best_child_puct`
- [x] `UCB1Policy` implementada com lógica extraída de `best_child_ucb`
- [x] `UCB1TunedPolicy` implementada com lógica extraída de `best_child_ucb_tuned`
- [x] `Optimizer.selection()` delega para política injetada via config

## Knowledge-Bias UCT + Limites
- [x] `max_depth` adicionado ao `MCTSConfig` com validação
- [x] `sufficiency_threshold` adicionado ao `MCTSConfig` com validação
- [x] `knowledge_bias_lambda` adicionado ao `MCTSConfig` com validação
- [x] Expansão bloqueada quando `depth >= max_depth`
- [x] Nó marcado como suficiente quando score > `sufficiency_threshold`
- [x] Score de seleção combina prior com Q-value via `knowledge_bias_lambda`

## Validações de Qualidade
- [x] Score clampado em [0, 1] na função de recompensa com warning
- [x] Warning emitido quando `manteve_regras_criticas=False` mas score > 0
- [x] Contadores de sucesso/falha de expansão por estratégia registrados
- [x] Métrica de eficiência de expansão emitida via `emit_cost`
- [x] Reward validado e clampado no `backpropagation`
- [x] Estatísticas de convergência (variância Q-value) emitidas ao final

## Rastreamento de Métricas DSPY
- [x] Latência de chamada LLM adicionada ao `CostEventPayload`
- [x] Taxa de sucesso de compilação registrada no log
- [x] `AlignConfig` criado unificando `MCTSConfig` + parâmetros DSPY
- [x] `load_align_config()` implementado com variáveis de ambiente

## Documentação
- [x] Justificativas MCTS documentadas (Swiechowski et al.)
- [x] Justificativas DSPY documentadas (signatures, modules, optimizers)
- [x] Guia de manutenção para sessões de pairing futuras criado

## Testes Integrados
- [x] `test_mcts.py` passa sem regressões (21/21)
- [x] `test_dspy_signatures.py` passa sem regressões (39/39)
- [x] `test_optimizer.py` passa sem regressões (12/12)
- [x] `test_optimizer_integration.py` passa sem regressões
- [x] `test_teleprompter.py` passa sem regressões (13/13)
- [x] Métricas de desempenho comparativas registradas (baseline pré-alinhamento)
