# Correção de Guardas de Qualidade do Output do Optimizer

## Why
O log do optimizer expõe 6 problemas que comprometem a confiabilidade do output final: (1) o sistema pode retornar uma skill pior que a original sem detectar, (2) há divergência entre reward bruto e score final reportado por aplicação inconsistente de multiplicadores e discount, (3) o `__DISCOVER__` gera quase só duplicatas conceituais (monocultura de "comprimir em SE→ENTÃO"), (4) os gates de qualidade (A/B e Post-Eval) aprovam tudo em modo warm-up sem casos de teste, (5) a recompensa por quebra de contrato é binária (0.00), sem gradiente para o MCTS, e (6) o alerta de plateau não interrompe iterações já em execução no batch corrente.

## What Changes
- **Guarda de "nunca retornar pior que a raiz"**: `_format_best_node` deve comparar o score do melhor nó com o score da raiz e, se for inferior, retornar a skill original com warning explícito.
- **Transparência na composição do score**: Log deve expor a cadeia completa de transformações (raw_reward → multipliers → delta_shaping → gamma_discount) para cada nó, eliminando a divergência 0.852 vs 0.589.
- **Restrição do `__DISCOVER__`**: Prompt de descoberta deve incluir exemplos explícitos dos 5 eixos de mutação para evitar monocultura; estratégias descobertas com 0% de sucesso após N tentativas devem ser despriorizadas.
- **Gate A/B e Post-Eval exigem casos mínimos**: Em modo warm-up (sem casos de teste), log deve emitir WARNING de incerteza alta em vez de aprovação silenciosa; gates só aprovam automaticamente se `len(test_cases) == 0` E `value_estimator.confidence < min_confidence`.
- **Recompensa gradual para quebra de contrato**: Em vez de `reward = 0.0` binário, aplicar penalty proporcional ao número de regras críticas violadas (`penalty = min(violated_count * 0.2, 1.0)`), preservando sinal de gradiente para o MCTS.
- **Plateau abort cancela futures do batch**: Quando `_abort_flag` é setado por plateau, chamar `executor.shutdown(wait=False, cancel_futures=True)` imediatamente em vez de apenas setar flag.

## Impact
- Affected specs: `align-mcts-dspy` (complementa validações de backprop/recompensa), `add-mutation-gate-composition`
- Affected code: `src/optimizer.py` (_format_best_node, _run_ab_gate, _run_post_eval, _run_single_iteration, _run_threaded_search, _discover_strategy, funcao_de_recompensa), `src/signatures.py` (funcao_de_recompensa), `src/domain/config.py` (MCTSConfig)

## ADDED Requirements

### Requirement: Guarda Anti-Regressão na Seleção Final
O sistema SHALL garantir que o output final nunca tenha score inferior ao da skill original (raiz). Se o melhor nó candidato tiver score < score da raiz, o sistema DEVE retornar a instrução original e emitir um WARNING explícito.

#### Scenario: Melhor nó tem score inferior à raiz
- **WHEN** o optimizer termina e `best_node.score < root.score`
- **THEN** o sistema retorna `root.instruction` (skill original)
- **AND** emite WARNING: "Nenhum candidato superou a skill original (root={root_score:.3f}, best={best_score:.3f}). Retornando original."

#### Scenario: Melhor nó tem score superior à raiz
- **WHEN** o optimizer termina e `best_node.score >= root.score`
- **THEN** o sistema retorna `best_node.instruction` normalmente

#### Scenario: Raiz é o único nó (zero filhos gerados)
- **WHEN** nenhum filho foi gerado durante a otimização
- **THEN** o sistema retorna `root.instruction` com WARNING: "Nenhuma expansão bem-sucedida. Retornando skill original."

### Requirement: Transparência na Cadeia de Score
O sistema SHALL logar a cadeia completa de transformações do score para cada nó avaliado: raw_reward → após multipliers → após delta_shaping → após gamma_discount → Q-value final (score reportado).

#### Scenario: Log de cadeia de score para nó avaliado
- **WHEN** uma iteração MCTS completa simulação e backpropagation
- **THEN** o log exibe: `[Score Chain] raw={raw:.3f} → mult={mult:.3f} → shaped={shaped:.3f} → discounted={disc:.3f} → Q/visits={score:.3f}`
- **AND** os valores são registrados no nó para inspeção pós-otimização

### Requirement: Diversificação do Prompt de Descoberta
O sistema SHALL enriquecer o prompt do `__DISCOVER__` com exemplos concretos dos 5 eixos de mutação (comprimir, expandir, reordenar, enriquecer, especializar) para evitar que o LLM gere apenas variações do mesmo eixo.

#### Scenario: Prompt de descoberta inclui exemplos dos 5 eixos
- **WHEN** `_discover_strategy` é chamado
- **THEN** o prompt enviado ao LLM inclui pelo menos um exemplo concreto de mutação para cada eixo (comprimir, expandir, reordenar, enriquecer, especializar)
- **AND** instrui explicitamente: "Gere uma estratégia de um eixo DIFERENTE dos já listados em estratégias conhecidas"

#### Scenario: Estratégia descoberta com 0% de sucesso é despriorizada
- **WHEN** uma estratégia descoberta via `__DISCOVER__` tem 0 expansões bem-sucedidas após 3 tentativas
- **THEN** o sistema emite WARNING e reduz o prior dela no bandit para 0.1x do default

### Requirement: Gates de Qualidade com Incerteza Explícita
O sistema SHALL emitir WARNING de incerteza alta quando gates operam sem casos de teste, em vez de aprovar silenciosamente.

#### Scenario: Gate A/B sem casos de teste
- **WHEN** `_run_ab_gate` é chamado com `test_cases` vazio
- **THEN** o sistema emite WARNING: "[Gate A/B] Operando sem casos de feedback — incerteza alta. Aprovação condicional (warm-up)."
- **AND** registra métrica `gates_without_test_cases` incrementada

#### Scenario: Post-Eval sem casos de teste
- **WHEN** `_run_post_eval` é chamado com `test_cases` vazio
- **THEN** o sistema emite WARNING: "[Post-Eval] Operando sem casos de teste — incerteza alta. Aprovação condicional (warm-up)."
- **AND** registra métrica `post_evals_without_test_cases` incrementada

### Requirement: Recompensa Gradual para Quebra de Contrato
O sistema SHALL substituir a recompensa binária (0.00) por violação de regras críticas por uma penalidade gradual proporcional à severidade da violação.

#### Scenario: Violação parcial de regras críticas
- **WHEN** `manteve_regras_criticas` é False e `defeitos_encontrados` contém N itens
- **THEN** o score é `max(0.05, base_score - min(N * 0.20, 0.80))` em vez de 0.0
- **AND** o feedback inclui a contagem de violações: "N violações críticas detectadas"

#### Scenario: Violação total (muitos defeitos)
- **WHEN** `manteve_regras_criticas` é False e `defeitos_encontrados` tem >= 5 itens
- **THEN** o score mínimo é 0.05 (reserva sinal mínimo de gradiente para o MCTS)

#### Scenario: Nenhuma violação (caso normal)
- **WHEN** `manteve_regras_criticas` é True
- **THEN** comportamento existente é preservado (score composto pelas 6 dimensões)

### Requirement: Plateau Abort com Cancelamento de Futures
O sistema SHALL cancelar futures já submetidas do batch corrente quando o abort por plateau é acionado.

#### Scenario: Plateau detectado no meio de um batch
- **WHEN** `_run_single_iteration` retorna `should_break=True` por plateau (5 zeros consecutivos)
- **THEN** `_run_threaded_search` chama `executor.shutdown(wait=False, cancel_futures=True)` imediatamente
- **AND** emite log: "[Plateau Abort] Cancelando {N} iterações restantes do batch corrente."

#### Scenario: Plateau detectado entre batches
- **WHEN** `_abort_flag` é setado e um novo batch está prestes a iniciar
- **THEN** o loop principal em `_run_threaded_search` verifica `self._abort_flag` antes de `executor.submit` e não submete novas iterações

## MODIFIED Requirements

### Requirement: Função de Recompensa com Penalidade Gradual (modifica requisito de `align-mcts-dspy`)
A função `funcao_de_recompensa` em `src/signatures.py` SHALL ser estendida para aplicar penalidade gradual (não binária) quando `manteve_regras_criticas=False`.

#### Scenario: Penalidade gradual substitui binária
- **WHEN** `manteve_regras_criticas` é False
- **THEN** o score = `max(0.05, composite_score - penalty)` onde `penalty = min(len(defeitos) * 0.20, 0.80)`
- **AND** NÃO retorna mais 0.0 fixo

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
