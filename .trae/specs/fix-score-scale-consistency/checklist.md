# Checklist

## Escala Canônica (raw_reward) Unificada
- [x] `best_reward_so_far` é atualizado com `raw_reward`, não `multiplied_reward`
- [x] `_save_checkpoint` salva `score=raw_reward` no JSON e no log
- [x] Poda relativa compara `estimated + 0.15` contra `best_reward_so_far` na mesma escala raw
- [x] `raw_reward` é passado como parâmetro explícito onde necessário (não inferido de `child.raw_reward`)

## Raiz na Mesma Escala
- [x] `root.raw_reward` é populado em `_evaluate_root` (single sample ou mediana)
- [x] `root.raw_reward` é acessível para comparação em `_format_best_node`
- [x] Guarda anti-regressão compara `best_child.raw_reward < root.raw_reward`
- [x] WARNING de regressão exibe valores na escala raw_reward

## Transparência de Log
- [x] `[ITER X/Y]` exibe `raw_reward` como valor primário
- [x] `multiplied_reward` e `shaped_reward` aparecem apenas quando |diff| > 0.05
- [x] `[Score Chain]` destaca `raw_reward` como valor canônico para comparações

## Prior Boosting Consistente
- [x] `load_priors` valida que `mean_reward` está em [0, 1]
- [x] Estratégias com `mean_delta < 0` recebem `virtual_count = 1` com log informativo
- [x] `ExperienceStore` armazena `absolute_reward` (multiplied_reward) mas `load_priors` do bandit usa `mean_delta` (shaped_reward) — escala consistente para navegação

## Tabela "Custo por Aprovação"
- [x] Todas as estratégias com `successful_expansions > 0` aparecem na tabela
- [x] Estratégias sem custo LLM registrado mostram "sem custo LLM registrado"

## Testes
- [x] `test_optimizer.py` passa sem regressões (7/7)
- [x] `test_optimizer_integration.py` passa sem regressões (4/4)
- [x] `test_mcts.py` passa sem regressões (11/11)
- [x] `test_bandit.py` passa sem regressões (26/26)
