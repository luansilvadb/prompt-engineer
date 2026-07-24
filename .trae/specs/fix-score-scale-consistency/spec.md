# Unificação de Escala de Score no Pipeline MCTS Spec

## Why
O pipeline MCTS utiliza três escalas de score diferentes (`raw_reward`, `multiplied_reward`, `shaped_reward → Q/visits`) de forma intercambiável sob o nome genérico de "score" ou "reward". Isso contamina a poda relativa (que compara contra `best_reward_so_far` na escala `multiplied_reward` inflada), a seleção final (que usa `Q/visits` pós-desconto), e a guarda anti-regressão (que compara `Q/visits` do filho contra `Q/visits` da raiz — valores acumulados em pipelines diferentes). A raiz nunca passa por multipliers nem delta-shaping, enquanto os filhos passam por toda a cadeia, tornando qualquer comparação entre raiz e filhos inerentemente inválida. O resultado prático: eficiência de expansão baixa (15.8%), suspeita de regressão impossível de confirmar, e decisões de poda baseadas em um "recorde" artificialmente alto.

## What Changes
- **`best_reward_so_far` passa a rastrear `raw_reward`** (escala canônica de qualidade absoluta), não `multiplied_reward`. Isso unifica a régua usada pela poda relativa com a régua de qualidade real dos nós.
- **Guarda anti-regressão passa a comparar `raw_reward`** do melhor filho contra `raw_reward` da raiz, não `Q/visits` (que acumula shaped_reward em pipeline diferente).
- **Checkpoint salva `raw_reward`** como score canônico, em vez de `multiplied_reward`.
- **Log `[ITER X/Y]` exibe `raw_reward`** (qualidade absoluta) além do score de navegação atual (`multiplied_reward`), para transparência.
- **Log `[Score Chain]` ganha destaque do valor canônico** usado para comparações (raw_reward).
- **Prior boosting do bandit**: verificação de que o `virtual_count` é derivado de `raw_reward` histórico, não de `multiplied_reward` ou `shaped_reward`, evitando que estratégias ruins sejam priorizadas por escala inflada.
- **Tabela "Custo por aprovação"**: correção da agregação para incluir todas as estratégias com aprovações, não apenas a primeira encontrada.

## Impact
- Affected specs: `fix-output-quality-guards` (modifica a guarda anti-regressão e transparência de score)
- Affected code: `src/optimizer.py` (_run_mcts_iteration, _save_checkpoint, _run_single_iteration, _format_best_node, _evaluate_root), `src/domain/mcts.py` (MCTSNode — possível adição de campo canônico), `src/mutation_strategies/bandit.py` (load_priors — verificação de escala)

## ADDED Requirements

### Requirement: Escala Canônica Única para Comparações de Qualidade
O sistema SHALL usar `raw_reward` (saída direta de `funcao_de_recompensa`, sem multipliers, sem delta-shaping, sem gamma-discount) como a escala canônica para todas as comparações de qualidade entre nós: poda relativa, checkpoint de melhor nó, guarda anti-regressão e seleção final.

#### Scenario: best_reward_so_far usa raw_reward
- **WHEN** uma iteração MCTS completa a simulação com `raw_reward=0.71`
- **THEN** `best_reward_so_far` é atualizado comparando contra `raw_reward` (0.71), não contra `multiplied_reward` (0.852)
- **AND** a poda relativa compara `estimated + 0.15 < best_reward_so_far` usando a mesma escala raw

#### Scenario: Guarda anti-regressão compara raw_reward
- **WHEN** `_format_best_node` avalia se o melhor filho supera a raiz
- **THEN** a comparação usa `best_child.raw_reward` vs `root.raw_reward` (ou mediana das avaliações da raiz), NÃO `Q/visits`
- **AND** se `best_child.raw_reward < root.raw_reward`, retorna a instrução original com WARNING

#### Scenario: Checkpoint salva raw_reward
- **WHEN** um checkpoint é salvo porque o nó atual tem o melhor score até agora
- **THEN** o campo `score` no checkpoint contém `raw_reward`, não `multiplied_reward`
- **AND** o log `[Checkpoint]` exibe o raw_reward como score canônico

### Requirement: Avaliação da Raiz na Mesma Escala
O sistema SHALL armazenar `raw_reward` da raiz de forma explícita e acessível (`root.raw_reward`), garantindo que a raiz seja comparável aos filhos na escala canônica. Quando `n_samples > 1`, a mediana dos `raw_reward` é armazenada como `root.raw_reward`.

#### Scenario: Raiz com n_samples=1
- **WHEN** `_evaluate_root` é chamado com `n_samples=1`
- **THEN** `root.raw_reward = reward` (saída direta de `funcao_de_recompensa`)
- **AND** `root.last_reward` também é populado (compatibilidade)

#### Scenario: Raiz com n_samples=5
- **WHEN** `_evaluate_root` é chamado com `n_samples=5`
- **THEN** 5 chamadas a `funcao_de_recompensa` são feitas, a mediana é armazenada em `root.raw_reward`
- **AND** `root.last_reward` = mediana (compatibilidade)

### Requirement: Transparência de Escala no Log de Iteração
O sistema SHALL exibir `raw_reward` no log `[ITER X/Y]` como o valor primário de qualidade, com `multiplied_reward` e `shaped_reward` como informações suplementares quando divergirem significativamente.

#### Scenario: Log de iteração com escalas divergentes
- **WHEN** `raw_reward=0.71`, `multiplied_reward=0.85`, `shaped_reward=0.59`
- **THEN** o log exibe: `[ITER 1/10] ... raw=0.711 | mult=0.852 | shaped=0.589 | depth=1`
- **AND** o valor `raw` é o primeiro e mais destacado

#### Scenario: Log de iteração com escalas próximas
- **WHEN** `raw_reward=0.71`, `multiplied_reward=0.73`, `shaped_reward=0.70`
- **THEN** o log exibe: `[ITER 1/10] ... raw=0.711 | depth=1` (mult e shaped omitidos por redundância)

### Requirement: Prior Boosting Consistente com Escala Canônica
O sistema SHALL verificar que os priors do `MutationBandit.load_priors` são derivados de `raw_reward` (ou delta de raw_reward), não de `multiplied_reward` ou `shaped_reward`. Se os priors armazenados no `ExperienceStore` estiverem em escala diferente, o sistema DEVE emitir WARNING.

#### Scenario: Prior derivado de raw_reward
- **WHEN** `load_priors` carrega estatísticas do ExperienceStore
- **THEN** o sistema verifica se `avg_reward` e `avg_delta` das estatísticas estão na escala [0, 1] de raw_reward
- **AND** se valores > 1.0 ou < 0.0 forem detectados, emite WARNING: "Possível inconsistência de escala nos priors do bandit"

#### Scenario: Mutador Cognitivo com delta negativo NÃO recebe boost
- **WHEN** uma estratégia tem `avg_delta < 0` nas estatísticas históricas
- **THEN** o `virtual_count` para essa estratégia é no máximo 1 (mínimo), independentemente do `cognitivo_prior_count`
- **AND** o log informa: "Estratégia X tem desempenho histórico negativo (avg_delta=Y), virtual_count reduzido para 1"

### Requirement: Correção da Tabela "Custo por Aprovação"
O sistema SHALL agregar corretamente todas as estratégias com aprovações na tabela final "Custo por aprovação", não apenas a primeira encontrada.

#### Scenario: Duas estratégias com aprovações
- **WHEN** "Preservação Seletiva de Blocos" tem 1/1 aprovação e "Compressão e Formalização" tem 1/1 aprovação
- **THEN** ambas aparecem na tabela "Custo por aprovação" com seus respectivos custos

## MODIFIED Requirements

### Requirement: Guarda Anti-Regressão (modifica requisito de `fix-output-quality-guards`)
O método `_format_best_node` SHALL ser modificado para:
1. Comparar `best_child.raw_reward` contra `root.raw_reward` (não `Q/visits` contra `Q/visits`)
2. Usar `root.raw_reward` (armazenado explicitamente em `_evaluate_root`) como referência
3. Emitir WARNING com ambos os valores na mesma escala (raw) quando ocorrer regressão

#### Scenario: Melhor filho com raw_reward inferior à raiz
- **WHEN** `best_child.raw_reward=0.59` e `root.raw_reward=0.66`
- **THEN** sistema retorna `root.instruction` com WARNING: "Nenhum candidato superou a skill original (root_raw=0.660, best_raw=0.590). Retornando original."

#### Scenario: Melhor filho com raw_reward superior à raiz
- **WHEN** `best_child.raw_reward=0.72` e `root.raw_reward=0.66`
- **THEN** sistema retorna `best_child.instruction` normalmente

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
