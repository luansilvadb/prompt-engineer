# Checklist

## Guarda Anti-Regressão
- [x] `_format_best_node` compara `best_node.score` com `root.score` e retorna `root.instruction` se inferior
- [x] WARNING é emitido com scores da raiz e do melhor nó quando ocorre regressão
- [x] `optimize()` nunca retorna instrução com score inferior ao da raiz sem aviso explícito
- [x] Caso sem filhos gerados retorna raiz com WARNING apropriado

## Transparência de Score
- [x] Campos `raw_reward`, `multiplied_reward`, `shaped_reward` estão presentes em `MCTSNode`
- [x] Log `[Score Chain]` aparece ao final de cada iteração com a cadeia completa
- [x] Valores da cadeia são consistentes: raw ≥ 0, multipliers aplicados corretamente, shaped dentro de [0,1]

## Diversificação do __DISCOVER__
- [x] Prompt de descoberta inclui exemplos concretos dos 5 eixos de mutação
- [x] Prompt instrui explicitamente a gerar estratégia de eixo diferente dos conhecidos
- [x] Estratégias com 0% de sucesso após 3 tentativas têm prior reduzido no bandit
- [x] Log registra quando uma estratégia descoberta é despriorizada

## Gates com Incerteza Explícita
- [x] `_run_ab_gate` emite WARNING (não INFO) quando `test_cases` vazio
- [x] `_run_post_eval` emite WARNING quando `test_cases` vazio
- [x] Contadores de gates sem casos de teste aparecem nas estatísticas finais
- [x] Mensagem de WARNING menciona "incerteza alta" e "warm-up"

## Recompensa Gradual
- [x] `funcao_de_recompensa` não retorna mais 0.0 fixo quando `manteve_regras_criticas=False`
- [x] Penalidade é proporcional ao número de defeitos: `min(len(defeitos) * 0.20, 0.80)`
- [x] Score mínimo é 0.05 (nunca zero) para preservar gradiente MCTS
- [x] Log informa contagem de violações e score resultante

## Plateau Abort com Cancelamento
- [x] `_run_threaded_search` chama `executor.shutdown(wait=False, cancel_futures=True)` ao detectar plateau
- [x] Log exibe contagem de iterações canceladas no batch corrente
- [x] `_run_single_iteration` verifica `_abort_flag` antes de chamar `_run_mcts_iteration`
- [x] Loop principal não submete novo batch quando `_abort_flag` está setado
- [x] Testes existentes (`test_optimizer.py`, `test_optimizer_integration.py`) passam sem regressão
