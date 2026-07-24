# Tasks

- [x] Task 1: Adicionar novos parâmetros de controle de custo ao `MCTSConfig`
  - [x] SubTask 1.1: Adicionar `iteration_timeout_s` (padrão 300), `iteration_llm_call_limit` (padrão 50), `composite_timeout_s` (padrão 45) ao dataclass `MCTSConfig` em `src/domain/config.py`, com validações bounds (min 30s, min 10 calls, min 20s respectivamente)
  - [x] SubTask 1.2: Adicionar leitura via variáveis de ambiente `MCTS_ITERATION_TIMEOUT_S`, `MCTS_ITERATION_LLM_CALL_LIMIT`, `MCTS_COMPOSITE_TIMEOUT_S` em `load_mcts_config()`

- [x] Task 2: Implementar circuit breaker por iteração
  - [x] SubTask 2.1: Modificar `_run_single_iteration` em `src/optimizer.py` para monitorar tempo decorrido e `_llm_call_count`; ao exceder `iteration_timeout_s` ou `iteration_llm_call_limit`, abortar a iteração sem incrementar `consecutive_zeros`
  - [x] SubTask 2.2: Garantir que o abort por circuit breaker emita log específico: "[Circuit Breaker] Iteração excedeu teto de {N}s/{M} chamadas LLM. Abortando." e NÃO conta como plateau

- [x] Task 3: Implementar timeout reduzido para etapas de composição
  - [x] SubTask 3.1: Modificar `_try_generate_mutation` em `src/optimizer.py` para aceitar parâmetro opcional `timeout_override`; quando chamado de fluxo de composição, usar `composite_timeout_s`
  - [x] SubTask 3.2: Passar `timeout_override=config.composite_timeout_s` nas chamadas de `_try_generate_mutation` dentro do loop de composição em `_expand_node`

- [x] Task 4: Implementar abordagem gradativa de estratégias
  - [x] SubTask 4.1: Modificar `_expand_node` para que, quando `tentativa == 1` e a tentativa 0 foi uma estratégia isolada que falhou no gate, force seleção de composição com 2 estratégias (limite temporário de `composition_max_strategies`=2)
  - [x] SubTask 4.2: Quando `tentativa == 2` e a tentativa 1 (composição de 2) falhou, force composição com 3 estratégias
  - [x] SubTask 4.3: Se o bandit já selecionou composição naturalmente na tentativa 0, NÃO aplicar redução (respeitar escolha do bandit)
  - [x] SubTask 4.4: Adicionar logs claros indicando a progressão: "Tentativa 1/3: estratégia isolada", "Tentativa 2/3: composição (2 eixos)", "Tentativa 3/3: composição (3 eixos)"

- [x] Task 5: Implementar rastreamento de custo por estratégia no bandit
  - [x] SubTask 5.1: Adicionar campos `_total_llm_calls: dict[str, int]`, `_estimated_tokens: dict[str, int]`, `_successful_expansions: dict[str, int]` ao `MutationBandit` em `src/mutation_strategies/bandit.py`
  - [x] SubTask 5.2: Adicionar método `record_cost(strategy_key: str, llm_calls: int, estimated_tokens: int, success: bool)` ao `IMutationBandit` e `MutationBandit`
  - [x] SubTask 5.3: Chamar `record_cost` de `_commit_iteration` no `Optimizer` quando uma expansão é concluída (com sucesso ou falha)
  - [x] SubTask 5.4: Expor custo médio por aprovação no `_log_final_stats`: `custo_por_aprov = total_llm_calls / max(1, successful_expansions)`
  - [x] SubTask 5.5: Aplicar penalidade UCB baseada em custo: estratégias com `custo_por_aprov > mediana * 1.5` recebem penalidade de até -0.30 no score UCB, proporcional ao excesso

- [x] Task 6: Implementar checkpoint do melhor nó
  - [x] SubTask 6.1: Em `_commit_iteration`, quando `reward > best_reward_so_far` (verificar antes do update do `best_reward_so_far`), gravar `outputs/strategies/checkpoint_{job_id}.json` com instruction, score, strategy, depth, timestamp, iteration
  - [x] SubTask 6.2: Garantir que o diretório `outputs/strategies/` exista antes de gravar (criar se necessário)
  - [x] SubTask 6.3: Emitir log: "[Checkpoint] Melhor nó salvo: score={reward:.3f}, strategy={strategy}, depth={depth}"

- [x] Task 7: Adicionar transparência ao multiplicador de densidade
  - [x] SubTask 7.1: Modificar `_apply_density_multiplier` em `src/optimizer.py` para logar razão `child_len/parent_len` e o raw multiplier antes do clamp
  - [x] SubTask 7.2: Adicionar contador de penalidades no piso (`_density_at_floor_count`) e emitir WARNING quando >80% das últimas 10 penalidades estão no piso (`density_multiplier_min`)

- [x] Task 8: Testes de validação
  - [x] SubTask 8.1: Teste unitário do circuit breaker (config) em `tests/test_cost_controls.py::TestCircuitBreakerConfig`
  - [x] SubTask 8.2: Teste unitário da abordagem gradativa em `tests/test_cost_controls.py::TestGradativeApproach`
  - [x] SubTask 8.3: Teste unitário de `record_cost` no bandit e penalidade UCB em `tests/test_cost_controls.py::TestBanditCostTracking`
  - [x] SubTask 8.4: Teste unitário de checkpoint em `tests/test_cost_controls.py::TestCheckpoint`
  - [x] SubTask 8.5: Teste unitário do log de densidade e WARNING de piso em `tests/test_cost_controls.py::TestDensityTransparency`
  - [x] SubTask 8.6: Teste unitário validando novos parâmetros no `MCTSConfig` em `tests/test_cost_controls.py::TestConfigNewParams`

# Task Dependencies
- [Task 2] depends on [Task 1] (usa iteration_timeout_s e iteration_llm_call_limit)
- [Task 3] depends on [Task 1] (usa composite_timeout_s)
- [Task 4] depends on [Task 3] (chama _try_generate_mutation com timeout reduzido no fluxo de composição)
- [Task 5] é independente; pode rodar em paralelo com Tasks 1-4
- [Task 6] é independente; pode rodar em paralelo com Tasks 1-5
- [Task 7] é independente; pode rodar em paralelo com Tasks 1-6
- [Task 8] depends on [Task 1], [Task 2], [Task 3], [Task 4], [Task 5], [Task 6], [Task 7]
