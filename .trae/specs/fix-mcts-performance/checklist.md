# Checklist de Verificação

## Loop de Expansão e Fallback
- [x] `_try_fallback_strategy` não re-seleciona estratégia já presente em `failed_strategies`
- [x] `_try_fallback_strategy` retorna `None` após 5 tentativas sem encontrar estratégia válida
- [x] Log "Expandindo nó (Tentativa X/3)" mostra progressão real (1/3 → 2/3 → 3/3) com estratégias distintas
- [x] `failed_strategies` é atualizado antes da chamada a `_try_fallback_strategy`
- [x] Loop de 3 tentativas tem break explícito após exaustão

## Timeout em Chamadas LLM
- [x] `llm_timeout` adicionado ao `MCTSConfig` com default 60
- [x] `MCTS_LLM_TIMEOUT` carregável de variável de ambiente
- [x] `_discover_strategy` aborta após timeout sem travar o pipeline
- [x] `_try_generate_mutation` trata timeout como falha recuperável (próxima tentativa/estratégia)
- [x] Timeout não quebra o fluxo de cancelamento por usuário

## Virtual Count Mínimo no Bandit
- [x] `load_priors` usa `max(1, min(int(count * 0.5), 10))` em vez de `min(int(count * 0.5), 10)`
- [x] `cognitivo_prior_count` padrão alterado de 1 para 4 em `load_mcts_config()`
- [x] Mutador Cognitivo recebe virtual count >= 1 mesmo com `count=1` nos priors

## Threading em Batches
- [x] `_run_threaded_search` submete iterações em batches de `num_threads`
- [x] Batch aguarda todas as futures do batch antes de submeter o próximo
- [x] `consecutive_zeros` e `consecutive_api_errors` propagados corretamente entre batches
- [x] Cancelamento por usuário interrompe batches pendentes
- [x] `_abort_flag` interrompe submissão de novos batches

## Logs de Progressão
- [x] Cada iteração emite log com timestamp ISO-8601
- [x] Log inclui duração da iteração em ms ou segundos
- [x] Log inclui estratégia usada, recompensa e profundidade
- [x] Iterações com falha ou descarte também emitem log de progressão
- [x] Formato do log: `[ITER X/Y] timestamp | duração | strat=NOME | reward=VALOR | depth=N`

## Testes
- [x] `test_mcts.py` passa sem regressões (6/6)
- [x] `test_bandit.py` passa sem regressões (26/26)
- [x] `test_optimizer.py` passa sem regressões (15/15)
- [x] `test_optimizer_integration.py` passa sem regressões (4/4)
