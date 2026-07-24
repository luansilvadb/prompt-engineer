# Tasks

- [x] Task 1: Circuit Breaker preemptivo com cancelamento de future
  - [x] SubTask 1.1: Em `_run_mcts_iteration` (ou `_run_single_iteration`), criar `iteration_deadline = self._iteration_start_time + self.config.iteration_timeout_s` e usá-lo para calcular `remaining = iteration_deadline - now` antes de cada chamada `future.result(timeout=...)` em `_try_generate_mutation` e `simulation`
  - [x] SubTask 1.2: Envolver a chamada de `simulation(...)` (que avalia `child.instruction`) com `concurrent.futures.ThreadPoolExecutor(max_workers=1)` + `future.result(timeout=remaining)`, e chamar `future.cancel()` no `except TimeoutError`
  - [x] SubTask 1.3: Em `_check_iteration_abort`, antes de submeter nova chamada LLM, adicionar verificação `if time.perf_counter() > iteration_deadline: emit log "deadline já passado, abortando"; return True`
  - [x] SubTask 1.4: Garantir que quando o circuit breaker dispara, `self._iteration_circuit_broken = True` e os futures pendentes sejam cancelados (não só aguardados)

- [x] Task 2: Shaping com escala raw consistente
  - [x] SubTask 2.1: Em `_run_mcts_iteration` (linha ~1250), alterar `child.last_reward = reward` para `child.last_reward = raw_reward` (escala raw, não multiplied)
  - [x] SubTask 2.2: Em `_commit_iteration` (linha ~1149-1150), alterar `parent_reward = child.parent.last_reward` para `parent_reward = child.parent.raw_reward` (mantém escala raw ao longo do DAG)
  - [x] SubTask 2.3: Garantir que `_evaluate_root` já define `root.raw_reward` (verificar) e `root.last_reward = root.raw_reward` para o primeiro nível usar escala raw
  - [x] SubTask 2.4: Atualizar o log `[Score Chain]` para incluir `parent_raw={parent_reward:.3f}` e label de escala, permitindo auditoria da fórmula `shaped = 0.6*mult + 0.4*(mult - parent_raw)`

- [x] Task 3: Poda relativa com margem configurável e escala declarada
  - [x] SubTask 3.1: Adicionar `prune_relative_margin: float = 0.15` no `MCTSConfig` em `src/domain/config.py`, com validação `[0.0, 1.0]` e leitura via `MCTS_PRUNE_RELATIVE_MARGIN`
  - [x] SubTask 3.2: Em `_should_prune` (linha ~265), substituir o `+0.15` hardcoded por `self.config.prune_relative_margin`
  - [x] SubTask 3.3: Atualizar a mensagem de log `[Poda Relativa]` para declarar escala: `Estimado ({estimated:.2f} [raw] + {margin:.2f}) < melhor recompensa ({best:.2f} [raw])`

- [x] Task 4: Reserva pré-LLM do par (leaf, strategy_key)
  - [x] SubTask 4.1: Adicionar campo `reserved_strategies: set[str]` e `reservation_lock: threading.Lock` no `MCTSNode` em `src/domain/mcts.py` (ou reusar `lock` existente)
  - [x] SubTask 4.2: Em `_expand_node`, antes de chamar `_try_generate_mutation`, adquirir `leaf.reservation_lock` e testar `if strategy_key in leaf.reserved_strategies: emit log "já reservado por outra thread"; continue` (tentar próxima estratégia). Caso contrário, `leaf.reserved_strategies.add(strategy_key)` e liberar o lock
  - [x] SubTask 4.3: Após `_try_generate_mutation` (em sucesso ou falha), remover `strategy_key` de `leaf.reserved_strategies` dentro de `finally` para liberar a reserva
  - [x] SubTask 4.4: Garantir que a reserva é por-iteração (limpa ao fim de `_expand_node`) para não bloquear estratégias em iterações futuras

- [x] Task 5: Prior boosting condicional do Mutador Cognitivo
  - [x] SubTask 5.1: Em `Optimizer.__init__` (linhas 122-141), extrair a estatística de `mutador_cognitivo` do `coalesced` (se existir) e obter `observed_mean_delta`
  - [x] SubTask 5.2: Envolver o bloco de prior boosting hardcoded (linhas 131-141) em `if observed_mean_delta is None or observed_mean_delta > 0:`; no `else`, emitir log `prior boosting suprimido: mean_delta histórico={observed_mean_delta:.3f} <= 0`
  - [x] SubTask 5.3: Corrigir o log de prior boosting para mostrar o `virtual_count` efetivamente aplicado (resultado de `load_priors`), não o `config.cognitivo_prior_count` bruto

- [x] Task 6: Correção da dupla contagem de `_expansion_failure`
  - [x] SubTask 6.1: No bloco `else` (Gate A/B reprovou, linhas 974-983), adicionar `continue` explícito antes do fim do bloco para impedir re-execução do bloco genérico (linhas 985-995)
  - [x] SubTask 6.2: No bloco `else` (Post-Eval reprovou, linhas 963-972), adicionar `continue` explícito também, para consistência
  - [x] SubTask 6.3: Verificar que o caminho de "sucesso e candidato inválido" (não entra em `if sucesso and _is_candidate_valid`) também não duplique — garantir que só o bloco genérico (985-995) conte quando nenhuma ramificação `if/else` contou

- [x] Task 7: Diversificação do conjunto de estratégias
  - [x] SubTask 7.1: Adicionar 3 estratégias hardcoded em `_seed_hardcoded_strategies` de `src/mutation_strategies/registry.py`:
    - `variacao_tom` — "Variação de Tom e Registro" (ajustar formalidade, voz ativa/passiva, nível de detalhe)
    - `reestruturacao_formato` — "Reestruturação de Formato" (converter listas↔prose, reorganizar cabeçalhos, modular em sub-seções)
    - `especificacao_contexto` — "Especificação de Contexto de Uso" (explicitar pré-condições, restrições de domínio, exceções e bordas)
  - [x] SubTask 7.2: Garantir que cada estratégia tenha nome legível, prompt específico e descrição no registry
  - [x] SubTask 7.3: Relaxar o prompt do `__DISCOVER__` em `src/optimizer.py` (linhas ~374-391) removendo a enumeração restritiva "EIXOS DE MUTAÇÃO DISPONÍVEIS" e substituindo por instrução genérica "invente uma estratégia de mutação coerente com a skill, cobrindo um eixo ainda não explorado pelas estratégias existentes: {lista dinâmica dos nomes já registrados}"

- [x] Task 8: Testes de validação
  - [x] SubTask 8.1: Teste unitário do circuit breaker preemptivo — simular chamada LLM que excede `remaining` e verificar que `future.cancel()` é invocado e o log declara cancelamento (não post-mortem 3x)
  - [x] SubTask 8.2: Teste unitário do shaping consistente — construir nó filho com `raw=0.711, mult=0.852` e pai com `raw=0.66`, verificar `shaped ≈ 0.588` e que `last_reward` do filho é `raw_reward`
  - [x] SubTask 8.3: Teste unitário da reserva pré-LLM — simular duas threads concorrentes selecionando o mesmo `(leaf, strategy_key)` e verificar que apenas uma chama `_try_generate_mutation`
  - [x] SubTask 8.4: Teste unitário do prior boosting condicional — memória com `mean_delta=-0.582` suprime o boost e emite log declarado; `mean_delta=0.05` aplica normalmente
  - [x] SubTask 8.5: Teste unitário da contagem singular — Gate A/B reprovando incrementa `_expansion_failure` exatamente uma vez
  - [x] SubTask 8.6: Teste unitário do registry — verifica que há pelo menos 8 estratégias após inicialização (5 originais + 3 novas)
  - [x] SubTask 8.7: Executar `test_optimizer.py`, `test_mcts.py`, `test_bandit.py`, `test_optimizer_integration.py` e verificar passagem sem regressão

# Task Dependencies
- Task 2 (shaping) é independente e pode rodar em paralelo com Task 3 (poda) e Task 5 (prior boosting) e Task 6 (contagem)
- Task 1 (circuit breaker) é independente
- Task 4 (reserva pré-LLM) depende de leitura do `MCTSNode` (Task 4.1) — pode iniciar em paralelo
- Task 7 (diversificação) é independente
- Task 8 (testes) depende de Tasks 1-7
