# Tasks

- [x] Task 1: Adicionar campo `had_technical_error` no `MCTSNode`
  - [x] SubTask 1.1: Adicionar `had_technical_error: bool = False` ao `__init__` de `MCTSNode` em `src/domain/mcts.py`
  - [x] SubTask 1.2: Garantir que o campo sobreviva a merge de transposição (se um nó canônico já tem a flag, preservá-la)

- [x] Task 2: Propagar flag `had_technical_error` na simulação
  - [x] SubTask 2.1: Em `simulation()`, quando `feedback.startswith("Erro interno na avaliação")`, além de incrementar `_technical_error_count`, a flag é propagada no `_run_mcts_iteration` via `child.had_technical_error = True`
  - [x] SubTask 2.2: Em `_run_mcts_iteration`, após `simulation()` retornar com `raw_reward == 0.0` e feedback de erro técnico, setar `child.had_technical_error = True`

- [x] Task 3: Refatorar `_format_best_node` para veredito final explícito em todos os ramos
  - [x] SubTask 3.1: No ramo de nó filho aceito (linha ~1761), substituir `[+] Melhor no selecionado:` por `[Veredito Final] Nó aceito:`
  - [x] SubTask 3.2: No ramo de guarda anti-regressão (linha ~1748), adicionar `[Veredito Final] GUARDA ANTI-REGRESSÃO:` antes do return
  - [x] SubTask 3.3: No ramo de raiz como fallback (linha ~1754), adicionar `[Veredito Final] Nenhum filho superou a raiz:` antes do return

- [x] Task 4: Refatorar `_report_technical_errors` para vincular erro ao nó vencedor
  - [x] SubTask 4.1: Acessar nó vencedor via `self._best_node` (setado em `_format_best_node`)
  - [x] SubTask 4.2: Implementar os dois cenários: nó vencedor OK (mensagem com "foi avaliado com sucesso") vs nó vencedor contaminado (mensagem "ATENÇÃO CRÍTICA: O próprio nó vencedor")
  - [x] SubTask 4.3: Ajustar `optimize()` para chamar `_format_best_node` antes de `_report_technical_errors`

# Task Dependencies
- Task 2 depende de Task 1
- Task 3 depende de Task 1
- Task 4 depende de Task 2 e Task 3
- Tasks 2 e 3 podem ser feitas em paralelo após Task 1
