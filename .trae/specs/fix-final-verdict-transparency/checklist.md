# Checklist

- [x] `MCTSNode` possui campo `had_technical_error: bool = False` inicializado no `__init__`
- [x] `simulation()` sinaliza erro técnico de forma que o chamador possa setar `child.had_technical_error = True`
- [x] `_run_mcts_iteration` seta `child.had_technical_error = True` quando `raw_reward == 0.0` por erro técnico
- [x] `_format_best_node` emite `[Veredito Final] Nó aceito:` quando filho vence
- [x] `_format_best_node` emite `[Veredito Final] GUARDA ANTI-REGRESSÃO:` quando guarda dispara
- [x] `_format_best_node` emite `[Veredito Final] Nenhum filho superou a raiz:` quando raiz é fallback
- [x] `_report_technical_errors` reporta "nó vencedor foi avaliado com sucesso" quando `had_technical_error == False`
- [x] `_report_technical_errors` reporta "ATENÇÃO CRÍTICA: o próprio nó vencedor" quando `had_technical_error == True`
- [x] `optimize()` chama `_report_technical_errors` com acesso ao nó vencedor ou após `_format_best_node` com informação disponível
- [x] Nenhum log de veredito anterior foi removido sem substituição equivalente
