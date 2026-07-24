# Checklist

## Circuit Breaker Preemptivo
- [x] O teto de `iteration_timeout_s` é imposto via timeout em `future.result(timeout=remaining)` na chamada de `simulation`, não só em checkpoints entre estágios
- [x] Quando o teto é excedido, `future.cancel()` é invocado e o log declara cancelamento com tempo decorrido real (não 3x o teto)
- [x] Antes de submeter nova chamada LLM, o sistema consulta `iteration_deadline` e aborta se o deadline já passou
- [x] O `_check_iteration_abort` retorna `True` imediatamente quando deadline passou, sem aguardar próxima chamada

## Shaping com Escala Raw Consistente
- [x] `child.last_reward` armazena `raw_reward` (não `multiplied_reward`) em `_run_mcts_iteration`
- [x] `_commit_iteration` usa `child.parent.raw_reward` (não `child.parent.last_reward` que era multiplied) como `parent_reward` em `calcular_delta_reward`
- [x] `root.last_reward = root.raw_reward` está definido em `_evaluate_root` para o primeiro nível
- [x] O log `[Score Chain]` revela `parent_raw={value}` e a escala usada
- [x] Para `raw=0.711, mult=0.852, parent_raw=0.66`, o `shaped` é ≈ 0.588 (não 0.589 com parent multiplied)

## Poda Relativa com Margem Configurável
- [x] `prune_relative_margin` existe no `MCTSConfig` com padrão 0.15 e validação `[0.0, 1.0]`
- [x] `MCTS_PRUNE_RELATIVE_MARGIN` é respeitada como variável de ambiente
- [x] `_should_prune` usa `self.config.prune_relative_margin` (não `+0.15` hardcoded)
- [x] O log `[Poda Relativa]` declara `Estimado (X [raw] + Y) < melhor recompensa (Z [raw])`

## Reserva Pré-LLM do Par (leaf, strategy_key)
- [x] `MCTSNode` tem `reserved_strategies: set[str]` e mecanismo de lock para reserva atômica
- [x] Duas threads concorrentes selecionando o mesmo `(leaf, strategy_key)` resultam em apenas uma chamada `_try_generate_mutation`
- [x] A reserva é liberada em `finally` após `_try_generate_mutation` (sucesso ou falha)
- [x] A reserva é por-iteração: não bloqueia estratégias em iterações futuras do mesmo nó

## Prior Boosting Condicional do Mutador Cognitivo
- [x] Quando a memória experiencial tem `mean_delta <= 0` para `mutador_cognitivo`, o boost hardcoded é suprimido
- [x] O log declara `prior boosting suprimido: mean_delta histórico={valor} <= 0` quando suprimido
- [x] O log de boost aplicado mostra o `virtual_count` efetivo (resultado de `load_priors`), não o `config.cognitivo_prior_count` bruto
- [x] Quando `mean_delta > 0` ou ausente, o boost é aplicado como antes

## Contagem Singular de Falhas de Expansão
- [x] O bloco `else` (Gate A/B reprovou) tem `continue` explícito e não re-executa o bloco genérico (linhas 985-995)
- [x] O bloco `else` (Post-Eval reprovou) tem `continue` explícito para consistência
- [x] `_expansion_failure[strategy_key]` é incrementado exatamente uma vez por falha real
- [x] A taxa de eficiência de expansão não é mais inflada pela dupla contagem

## Diversificação do Conjunto de Estratégias
- [x] O `StrategyRegistry` contém pelo menos 8 estratégias hardcoded após inicialização (5 originais + 3 novas: `variacao_tom`, `reestruturacao_formato`, `especificacao_contexto`)
- [x] Cada nova estratégia tem nome legível e prompt específico cobrindo eixo distinto
- [x] O prompt do `__DISCOVER__` não enumera mais "EIXOS DE MUTAÇÃO DISPONÍVEIS" fixos; lista dinamicamente os nomes registrados e pede eixo não explorado
- [x] As 5 estratégias originais continuam funcionando sem regressão

## Testes
- [x] `test_optimizer.py` passa sem regressões
- [x] `test_mcts.py` passa sem regressões
- [x] `test_bandit.py` passa sem regressões
- [x] `test_optimizer_integration.py` passa sem regressões
- [x] Novo teste do circuit breaker preemptivo passa
- [x] Novo teste do shaping consistente passa
- [x] Novo teste da reserva pré-LLM passa
- [x] Novo teste do prior boosting condicional passa
- [x] Novo teste da contagem singular passa
- [x] Novo teste do registry com 8 estratégias passa
