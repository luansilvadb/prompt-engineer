# Checklist

- [x] O `StrategyRegistry` contém 5 estratégias hardcoded após inicialização: mutador_cognitivo, compressao_formalizacao, enriquecimento_exemplos, reorganizacao_falha, preservacao_blocos
- [x] Cada uma das 4 novas estratégias tem um prompt imperativo descrevendo seu eixo técnico Distinto (compressão, enriquecimento, reorganização, preservação)
- [x] O `SqliteExperienceStore` expõe `get_feedback_frequency(top_k)` retornando feedbacks ordenados por menor delta_reward
- [x] O `SqliteExperienceStore` expõe `get_effective_blocks(top_k)` retornando trechos de instruction com delta_reward > 0
- [x] O `SqliteExperienceStore` expõe `get_ab_test_cases(skill_hash, top_k)` retornando casos de feedback relevantes por skill_hash
- [x] O `Optimizer` tem método `_run_ab_gate` que compara scores de original vs mutada contra casos de feedback
- [x] O gate A/B aprova apenas mutações cujo score médio supera o original por margem mínima configurável
- [x] O `_expand_node` integra o gate A/B após validação estrutural, rejeitando mutações sem melhoria empírica
- [x] A estratégia de reorganização recebe frequências de erro do experience store injetadas no prompt
- [x] A estratégia de preservação recebe blocos eficazes do experience store injetados no prompt
- [x] Mutações que falham no gate A/B são marcadas como failed_strategies e não geram nó filho
- [x] `MCTSConfig` tem parâmetro `ab_margin_min` configurável via variável de ambiente
- [x] Teste unitário valida que o registry inicializa com as 5 estratégias
- [x] Teste unitário valida aprovação e rejeição do gate A/B
- [x] Nenhuma mutação é aceita apenas com base em forma textual — todas passam pelo gate A/B empírico
