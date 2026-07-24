# Tasks

- [x] Task 1: Corrigir loop de expansão e fallback de estratégia no `_expand_node`
  - [x] SubTask 1.1: Garantir que `_try_fallback_strategy` não re-selecione estratégia já em `failed_strategies`, com limite de 5 tentativas e log de warning se a mesma estratégia for retornada
  - [x] SubTask 1.2: Mover log "Expandindo nó (Tentativa X/3)" para dentro do bloco condicional que só executa com estratégia válida, e garantir que `failed_strategies` seja atualizado antes de `_try_fallback_strategy`
  - [x] SubTask 1.3: Adicionar break explícito após 3 falhas consecutivas para evitar loop residual

- [x] Task 2: Adicionar timeout em chamadas LLM
  - [x] SubTask 2.1: Adicionar `llm_timeout` ao `MCTSConfig` com valor padrão 60s, carregável via env `MCTS_LLM_TIMEOUT`
  - [x] SubTask 2.2: Instrumentar `_discover_strategy` com timeout via `concurrent.futures.ThreadPoolExecutor` ou `threading.Timer`
  - [x] SubTask 2.3: Instrumentar `_try_generate_mutation` com detecção de timeout e tratamento como falha recuperável

- [x] Task 3: Corrigir virtual count mínimo no `MutationBandit.load_priors`
  - [x] SubTask 3.1: Alterar `virtual_count = min(int(stats['count'] * 0.5), 10)` para `virtual_count = max(1, min(int(stats['count'] * 0.5), 10))`
  - [x] SubTask 3.2: Alterar default `cognitivo_prior_count` de 1 para 4 em `load_mcts_config()`

- [x] Task 4: Refatorar `_run_threaded_search` para batches controlados
  - [x] SubTask 4.1: Substituir submissão única de todas as iterações por loop de batches de tamanho `num_threads`
  - [x] SubTask 4.2: Garantir que `consecutive_zeros` e `consecutive_api_errors` sejam corretamente propagados entre batches

- [x] Task 5: Adicionar logs de progressão detalhados com timestamp e latência
  - [x] SubTask 5.1: Adicionar medição de tempo por iteração com `time.perf_counter()` em `_run_single_iteration`
  - [x] SubTask 5.2: Emitir log formatado: `[ITER X/Y] timestamp | duração | strat=NOME | reward=VALOR | depth=N`
  - [x] SubTask 5.3: Garantir que logs de progressão sejam emitidos mesmo em iterações com falha ou descarte

- [x] Task 6: Executar e validar testes
  - [x] SubTask 6.1: Executar `test_mcts.py` e verificar passagem sem regressões
  - [x] SubTask 6.2: Executar `test_bandit.py` e verificar passagem sem regressões
  - [x] SubTask 6.3: Executar `test_optimizer.py` e verificar passagem sem regressões
  - [x] SubTask 6.4: Executar `test_optimizer_integration.py` e verificar passagem sem regressões

# Task Dependencies
- Task 1 (expansão/fallback) é independente e pode ser executada primeiro
- Task 2 (timeout LLM) é independente
- Task 3 (virtual count) é independente
- Task 4 (batches) é independente
- Task 5 (logs) depende de Task 1 e Task 4 (precisa do loop corrigido para medição precisa)
- Task 6 (testes) depende de Tasks 1-5
