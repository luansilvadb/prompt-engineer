# Transparência do Veredito Final e Vinculação de Erro Técnico ao Nó Vencedor Spec

## Why
Duas lacunas de transparência foram identificadas após a correção de infraestrutura (`fix-post-eval-circuit-breaker-and-schema`):

1. **Linha de confirmação do veredito final ausente**: O log termina em `Skill otimizada preservada...` sem declarar explicitamente qual nó foi escolhido como resultado final, com qual score e qual estratégia. A linha `[+] Melhor no selecionado:` existe no código (linha 1761 de `_format_best_node`), mas só é emitida em um ramo condicional específico — se a guarda anti-regressão disparar ou se o nó for a raiz, o veredito fica implícito, obrigando o operador a inferir o resultado pelo contexto. Isso é especialmente crítico agora que o próprio sistema admite que parte da execução pode não ser confiável (alerta de % de erros técnicos).

2. **Alerta de erro técnico genérico**: `_report_technical_errors()` (linha 1901) reporta apenas o total de avaliações que falharam por erro técnico e a porcentagem global, sem informar se o erro atingiu especificamente o nó que foi escolhido como vencedor. O operador precisa cruzar manualmente os logs para saber se o resultado final está contaminado ou não.

## What Changes
- **Veredito final explícito**: `_format_best_node` emitirá SEMPRE uma linha de veredito final, em todos os ramos (nó vencedor, guarda anti-regressão, raiz como fallback), com score, raw_reward, estratégia e profundidade.
- **Rastreamento de erro técnico por nó**: Adicionar flag `had_technical_error` em `MCTSNode` para marcar nós cuja simulação falhou por erro técnico (não score zero real). No `_report_technical_errors`, verificar se o nó vencedor foi afetado e reportar explicitamente: "o nó vencedor foi avaliado com sucesso; N outras avaliações falharam" ou "ATENÇÃO: o próprio nó vencedor teve sua avaliação comprometida por erro técnico".

## Impact
- Affected specs: `fix-post-eval-circuit-breaker-and-schema` (complementa a transparência introduzida pelo alerta de %)
- Affected code:
  - `src/domain/mcts.py` — `MCTSNode`: adicionar campo `had_technical_error: bool = False`
  - `src/optimizer.py` — `simulation()`: retornar (ou sinalizar via nó) se foi erro técnico; `_run_mcts_iteration`: propagar flag para `child`; `_format_best_node`: emitir veredito final em TODOS os ramos; `_report_technical_errors`: verificar nó vencedor e customizar mensagem

## ADDED Requirements

### Requirement: Veredito Final Explícito em Todos os Ramos
O sistema SHALL emitir uma linha de log de veredito final explícita ao concluir `_format_best_node`, independentemente do ramo tomado pela lógica de seleção.

#### Scenario: Nó filho vence (caso normal)
- **WHEN** `best_node != root` E `comparison_value >= root.raw_reward`
- **THEN** o sistema emite `[Veredito Final] Nó aceito: score={best_score:.3f}, raw={best_node.raw_reward:.3f}, strategy={strategy_desc}, depth={best_node.depth}` ANTES de retornar `best_node.instruction`

#### Scenario: Guarda anti-regressão dispara
- **WHEN** `best_node != root` E `comparison_value < root.raw_reward`
- **THEN** o sistema emite `[Veredito Final] GUARDA ANTI-REGRESSÃO: melhor nó rejeitado (raw={comparison_value:.3f} < raiz raw={root.raw_reward:.3f}). Retornando skill original.` ANTES de retornar `root.instruction`

#### Scenario: Raiz é o único nó (fallback)
- **WHEN** `best_node == root`
- **THEN** o sistema emite `[Veredito Final] Nenhum filho superou a raiz. Retornando skill original. raw={root.raw_reward:.3f}, visits={root.visits}` ANTES de retornar `root.instruction`

### Requirement: Vinculação de Erro Técnico ao Nó Vencedor
O sistema SHALL rastrear, por nó, se a simulação falhou por erro técnico de infraestrutura, e reportar no alerta final se o nó vencedor foi especificamente afetado.

#### Scenario: Nó vencedor avaliado com sucesso, mas houve erros em outros nós
- **WHEN** `_technical_error_count > 0` E o nó vencedor NÃO teve erro técnico
- **THEN** o sistema emite `[!] ATENÇÃO: {tech_errors}/{total} avaliações ({pct:.1f}%) falharam por erro técnico. O nó vencedor (strategy={desc}, raw={score:.3f}) foi avaliado com sucesso — o resultado final não está contaminado.`

#### Scenario: Nó vencedor foi afetado por erro técnico
- **WHEN** `_technical_error_count > 0` E o nó vencedor teve erro técnico (`had_technical_error == True`)
- **THEN** o sistema emite `[!] ATENÇÃO CRÍTICA: O próprio nó vencedor (strategy={desc}) teve sua avaliação comprometida por erro técnico. O resultado desta execução NÃO é confiável. {tech_errors}/{total} avaliações ({pct:.1f}%) falharam no total.`

#### Scenario: Nenhum erro técnico
- **WHEN** `_technical_error_count == 0`
- **THEN** comportamento atual mantido: `[*] Nenhum erro técnico de avaliação detectado ({total} avaliações realizadas).`

## MODIFIED Requirements

### Requirement: `_format_best_node` — Estrutura de Log
A estrutura atual de `_format_best_node` (linhas 1713-1768) é modificada para garantir que todo ramo de retorno emita uma linha `[Veredito Final]` antes do `return`. O log existente `[+] Melhor no selecionado:` é substituído pelo novo formato padronizado `[Veredito Final] Nó aceito:`.

### Requirement: `MCTSNode` — Campo `had_technical_error`
O modelo `MCTSNode` ganha o campo `had_technical_error: bool = False`, inicializado como `False` e setado para `True` quando `simulation()` detecta erro técnico (feedback começando com `"Erro interno na avaliação"`). O campo é propagado em `_run_mcts_iteration` após `simulation()` retornar.

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
