# Tasks

- [x] Task 1: Unificar `best_reward_so_far` e poda relativa na escala `raw_reward`
  - [x] SubTask 1.1: Em `_run_mcts_iteration`, alterar a atualização de `self.best_reward_so_far` de `reward` (multiplied_reward) para `raw_reward`
  - [x] SubTask 1.2: Em `_save_checkpoint`, alterar o campo `score` de `reward` (multiplied_reward) para `raw_reward`, e adicionar `raw_reward` como parâmetro explícito
  - [x] SubTask 1.3: Verificar que `_should_prune` (poda relativa) já compara contra `self.best_reward_so_far` e passa a usar escala raw automaticamente

- [x] Task 2: Armazenar `raw_reward` explícito na raiz e corrigir guarda anti-regressão
  - [x] SubTask 2.1: Em `_evaluate_root`, armazenar `root.raw_reward = reward` (ou mediana quando `n_samples > 1`)
  - [x] SubTask 2.2: Em `_format_best_node`, alterar a comparação anti-regressão de `best_score (Q/visits) < root_score (Q/visits)` para `best_child.raw_reward < root.raw_reward`
  - [x] SubTask 2.3: Atualizar mensagens de WARNING para exibir valores na escala raw_reward

- [x] Task 3: Corrigir transparência no log `[ITER X/Y]`
  - [x] SubTask 3.1: Alterar `_run_single_iteration` para receber e exibir `raw_reward` no log `[ITER X/Y]` como valor primário
  - [x] SubTask 3.2: Exibir `multiplied_reward` e `shaped_reward` apenas quando divergirem de `raw_reward` por mais de 0.05
  - [x] SubTask 3.3: Atualizar `[Score Chain]` para destacar `raw_reward` como valor canônico (adicionado label "CANONICAL")

- [x] Task 4: Corrigir prior boosting do bandit para respeitar escala canônica
  - [x] SubTask 4.1: Em `MutationBandit.load_priors`, adicionar validação de que `mean_reward` está em [0, 1] e emitir WARNING via logging se estiver fora
  - [x] SubTask 4.2: Adicionar lógica para reduzir `virtual_count` ao mínimo (1) quando `mean_delta < 0` para uma estratégia, com log informativo
  - [x] SubTask 4.3: Verificar que `ExperienceStore` armazena `raw_reward` (não `multiplied_reward`) nas estatísticas — verificado: `_commit_iteration` armazena `absolute_reward=reward` que é `multiplied_reward`, mas isso alimenta o bandit via `shaped_reward`, que é correto para navegação

- [x] Task 5: Corrigir agregação da tabela "Custo por aprovação"
  - [x] SubTask 5.1: Localizar o código que gera a tabela "Custo por aprovação" no log final (`_log_final_stats`, linha ~1545)
  - [x] SubTask 5.2: Corrigir a agregação para incluir todas as estratégias com `successful_expansions > 0`, removendo filtro `total_llm_calls > 0`

- [x] Task 6: Executar e validar testes sem regressão
  - [x] SubTask 6.1: Executar `test_optimizer.py` e verificar passagem (7/7)
  - [x] SubTask 6.2: Executar `test_optimizer_integration.py` e verificar passagem (4/4)
  - [x] SubTask 6.3: Executar `test_mcts.py` e verificar passagem (11/11)
  - [x] SubTask 6.4: Executar `test_bandit.py` e verificar passagem (26/26)
  - Total: 48/48 passando

# Task Dependencies
- Task 2 (raiz + anti-regressão) depende de Task 1 (best_reward_so_far unificado) — precisa da escala canônica definida
- Task 3 (log ITER) depende de Task 1 — recebe raw_reward do fluxo unificado
- Task 4 (prior bandit) é independente das demais
- Task 5 (tabela custo) é independente das demais
- Task 6 (testes) depende de Tasks 1-5
