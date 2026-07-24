# Correção de Race Condition entre Aprovação de Gate e Abort por Deadline Spec

## Why
A iteração 7 gerou uma mutação `variacao_tom` aprovada por ambos os gates com deltas grandes e positivos (+0.272 no Gate A/B, +0.650 no Post-Eval Comportamental), mas o sistema descartou esse resultado porque o deadline da iteração expirou entre a aprovação dos gates e a conclusão da simulação (`self.simulation()`). A estrutura de checkpoint (`_save_checkpoint`) e a propagação de recompensa (`_commit_iteration`, `backpropagation`) só são alcançadas após a simulação bem-sucedida (linha ~1346-1379 de `_run_mcts_iteration`). Quando a simulação sofre timeout, todo o trabalho de avaliação dos gates — que é caro e aprovou o candidato — é perdido: `child.raw_reward` permanece 0.0, o checkpoint nunca é salvo, e o bandit nunca é atualizado. O nó filho fica na árvore como "zumbi" (existe mas com valores zerados), e a guarda anti-regressão final compara contra um candidato desatualizado (iteração 1, raw=0.050), rejeitando uma melhoria real.

## What Changes
- **Time-gate antes dos gates de avaliação**: Antes de executar o Gate A/B e o Post-Eval Comportamental (que envolvem chamadas LLM caras), verificar `_remaining_time()` e abortar a iteração se o tempo restante for insuficiente para completar gates + simulação. Isso evita o trabalho desperdiçado que gera o "zumbi".
- **Fallback score para gate-approved candidates com simulação timeout**: Quando um candidato passa por ambos os gates mas a simulação sofre timeout, usar um `fallback_raw` derivado das pontuações dos gates (ex.: média ponderada de `score_mut` do Gate A/B e `post_score_mut` do Post-Eval, normalizada para a escala raw) em vez de descartar com `raw=0.0`. O fallback só é aplicado se ambos os gates aprovaram com margem positiva — candidates que nunca passaram pelos gates não recebem fallback.
- **Checkpoint antecipado para gate-approved candidates**: Após aprovação dupla dos gates e criação do `child`, salvar um "checkpoint provisório" com os scores dos gates, antes mesmo da simulação. Se a simulação falhar, o checkpoint provisório serve como ancoragem para a guarda final.
- **Log explícito de fallback**: Emitir `[Gate Fallback]` quando a simulação falha mas os gates aprovaram, declarando o `fallback_raw` e os scores de gate usados.

## Impact
- Affected specs: `fix-structural-bugs-round-2` (circuit breaker + diversificação criaram as condições para esta race condition), `fix-circuit-breaker-and-crash` (circuit breaker agora compete com checkpoint), `add-mutation-gate-composition` (gates são a fonte dos scores de fallback)
- Affected code:
  - `src/optimizer.py` — `_run_mcts_iteration` (linhas ~1297-1394): reordenar time-gates, adicionar fallback para simulation timeout com gate scores, salvar checkpoint provisório
  - `src/optimizer.py` — `_expand_node` (linhas ~940-1070): expor os scores dos gates (`score_mut` do Gate A/B e `post_score_mut` do Post-Eval) para uso no fallback
  - `src/domain/mcts.py` — possível campo `gate_score` ou `fallback_raw` no `MCTSNode` para armazenar o score de fallback

## ADDED Requirements

### Requirement: Time-Gate Preventivo Antes dos Gates de Avaliação
O sistema SHALL verificar se há tempo restante suficiente para completar gates + simulação antes de executar o Gate A/B e o Post-Eval Comportamental, abortando a iteração preventivamente se o orçamento for insuficiente.

#### Scenario: Tempo insuficiente antes dos gates
- **WHEN** `_remaining_time()` é menor que um limiar configurável `min_time_for_gates_s` (padrão 10s) antes da execução do Gate A/B
- **THEN** a iteração é abortada com log `[Circuit Breaker] Tempo restante insuficiente para gates + simulação. Abortando.`, sem executar os gates

#### Scenario: Tempo suficiente para gates
- **WHEN** `_remaining_time() >= min_time_for_gates_s` antes do Gate A/B
- **THEN** os gates executam normalmente; se aprovados, o sistema prossegue para simulação com o tempo restante

### Requirement: Fallback Score para Gate-Approved Candidates com Timeout de Simulação
O sistema SHALL preservar candidatos aprovados por ambos os gates mesmo quando a simulação sofre timeout, usando um `fallback_raw` derivado das pontuações dos gates em vez de descartar com `raw=0.0`.

#### Scenario: Simulação timeout após aprovação dupla
- **WHEN** um candidato foi aprovado pelo Gate A/B (com `score_mut`) e pelo Post-Eval Comportamental (com `post_score_mut`), mas `future.result(timeout=remaining)` lança `TimeoutError`
- **THEN** o sistema calcula `fallback_raw` a partir dos scores dos gates, define `child.raw_reward = fallback_raw`, executa `_commit_iteration` e `_save_checkpoint` normalmente, e emite log `[Gate Fallback] Simulação timeout. Usando fallback_raw={value} derivado dos gates (A/B={ab_score}, Post-Eval={post_score})`

#### Scenario: Timeout sem aprovação dos gates
- **WHEN** a simulação sofre timeout mas o candidato NÃO passou por ambos os gates (ex.: caminho que não executa gates, ou gate reprovou)
- **THEN** o comportamento atual é mantido: `raw=0.0`, sem checkpoint, sem backpropagation

### Requirement: Checkpoint Provisório para Gate-Approved Candidates
O sistema SHALL salvar um checkpoint imediatamente após a aprovação dupla dos gates e criação do `child`, antes da simulação, para ancorar o resultado mesmo se a simulação falhar.

#### Scenario: Checkpoint provisório salvo antes da simulação
- **WHEN** um candidato é aprovado por ambos os gates e `_create_child_node` retorna com sucesso
- **THEN** um checkpoint é salvo com os scores dos gates e a instrução do candidato, antes de iniciar a simulação, com log `[Checkpoint Provisório] Candidato gate-approved salvo: A/B={ab_score}, Post-Eval={post_score}`

#### Scenario: Simulação bem-sucedida sobrescreve checkpoint provisório
- **WHEN** a simulação completa com sucesso após o checkpoint provisório
- **THEN** o checkpoint definitivo é salvo com `raw_reward` da simulação (comportamento atual), sobrescrevendo o provisório

## MODIFIED Requirements

### Requirement: Ordem de Operações em `_run_mcts_iteration`
O método `_run_mcts_iteration` SHALL verificar o orçamento de tempo restante ANTES de iniciar operações caras (Gate A/B, Post-Eval, simulação), na seguinte ordem:

1. Selection + Expansion (já existente)
2. **Time-gate preventivo**: verificar `_remaining_time() >= min_time_for_gates_s` antes dos gates
3. Gate A/B + Post-Eval (dentro de `_expand_node`, já existente)
4. Após aprovação dos gates: salvar checkpoint provisório
5. Verificar `_remaining_time()` antes da simulação
6. Simulação com `future.result(timeout=remaining)`
7. Se timeout: aplicar fallback score; se sucesso: comportamento normal
8. `_commit_iteration` + `_save_checkpoint` (em ambos os casos de aprovação)

#### Scenario: Candidato aprovado sobrevive a timeout e é considerado na seleção final
- **WHEN** iteração 7 gera `variacao_tom` com Gate A/B score_mut=0.465 e Post-Eval score_mut=0.650, e a simulação sofre timeout
- **THEN** `child.raw_reward` é definido com fallback > 0 (não 0.0), `_commit_iteration` executa, checkpoint é salvo, e a guarda anti-regressão final compara contra um valor que reflete a aprovação real dos gates

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
