# Correção de Circuit Breaker Pós-Post-Eval e Schema Mismatch Spec

## Why
Duas falhas críticas foram confirmadas por logs concretos:

1. **Race condition residual**: As specs `fix-checkpoint-race-condition` e `fix-incremental-gate-checkpoint` implementaram checkpoint incremental entre gates e Gate Fallback para timeout de simulação. Porém, o circuit breaker ainda pode disparar **antes de `simulation()` iniciar** (linhas 1450-1457 de `_run_mcts_iteration`), quando o orçamento de tempo se esgota entre a aprovação do Post-Eval e o início da simulação. Neste cenário, o candidato — já aprovado por ambos os gates com deltas positivos — retorna `(True, 0.0)`, fica com `raw_reward=0.0`, e a guarda anti-regressão final o descarta (mesmo com o proxy de `gate_ab_score`, que pode ser menor que o raw da raiz). O Gate Fallback existente só cobre `TimeoutError` **durante** a simulação, não o abort **antes** dela.

2. **Schema mismatch (hyphen vs underscore)**: O LLM avaliador ocasionalmente retorna campos JSON com hífen (ex.: `nota_anti-fragilidade`) onde o parser DSPy espera underscore (`nota_anti_fragilidade`). O DSPy (`JSONAdapter`) rejeita o parse completo, a exceção é capturada pelo `except Exception` genérico em `funcao_de_recompensa`, e o resultado é `reward=0.00` — o pior score possível — para uma avaliação qualitativamente excelente (notas 95-99, "nenhum defeito encontrado"). O log expõe o conteúdo rico da avaliação perdida, mas o score final não o reflete.

## What Changes

### Bug 1: Circuit Breaker antes de simulation() com gates aprovados
- **Gate Fallback estendido para abort pré-simulação**: Quando `_check_iteration_abort()` retorna `True` ou `_remaining_time() <= 0` **após** o checkpoint provisório ter sido salvo (`child.gate_post_eval_score > 0`), aplicar a mesma lógica de Gate Fallback que já existe para `TimeoutError` — em vez de retornar `(True, 0.0)`, definir `child.raw_reward = child.gate_ab_score`, executar `_commit_iteration` e `_save_checkpoint`, e retornar `(False, fallback_raw)`.
- **Log específico**: `[Gate Fallback] Circuit breaker pré-simulação. Usando fallback_raw={value} do Gate A/B. Post-Eval={post_score}.` (diferente do log de timeout para facilitar diagnóstico).

### Bug 2: Schema mismatch hyphen vs underscore
- **Normalização de chaves no adapter DSPy**: Adicionar uma camada de normalização que converte hífens em underscores nos nomes de campos da resposta JSON do LLM **antes** do DSPy fazer o parse. Isso será feito via um wrapper customizado no `JudgeModule` que intercepta a resposta bruta do LM e normaliza as chaves.
- **Log explícito de normalização**: `[Schema Normalization] Chave 'nota_anti-fragilidade' normalizada para 'nota_anti_fragilidade'` — para que o operador saiba que houve correção silenciosa.
- **Instrução explícita no prompt**: Adicionar `(use underscore '_' not hyphen '-' in field names)` nas descrições dos `OutputField` críticos nas Signatures `AvaliadorDeSkillSignature` e `AvaliadorModoBSignature` como camada preventiva adicional.

## Impact
- Affected specs: `fix-checkpoint-race-condition` (estende o Gate Fallback para um novo ponto de disparo), `fix-incremental-gate-checkpoint` (o checkpoint incremental pós-Post-Eval agora tem seu valor totalmente aproveitado)
- Affected code:
  - `src/optimizer.py` — `_run_mcts_iteration` (linhas ~1450-1457): estender Gate Fallback para abort pré-simulação
  - `src/infrastructure/dspy_impl.py` — `JudgeModule.__call__`: adicionar normalização de chaves e instrução anti-hífen nos descritores
  - `src/signatures.py` — `funcao_de_recompensa`: opcionalmente, melhorar a mensagem de erro para distinguir "erro de schema/parsing" de "erro interno genérico"

## ADDED Requirements

### Requirement: Gate Fallback para Circuit Breaker Pré-Simulação
O sistema SHALL aplicar a lógica de Gate Fallback quando o circuit breaker disparar **antes** de `simulation()` iniciar, desde que o candidato já tenha sido aprovado por ambos os gates (`gate_post_eval_score > 0`).

#### Scenario: Circuit breaker dispara entre Post-Eval e simulation()
- **WHEN** `_check_iteration_abort()` retorna `True` ou `_remaining_time() <= 0` nas linhas 1450-1457 de `_run_mcts_iteration`, E `child.gate_post_eval_score > 0`
- **THEN** o sistema aplica Gate Fallback: `child.raw_reward = child.gate_ab_score`, executa `_commit_iteration`, `_save_checkpoint`, emite log `[Gate Fallback] Circuit breaker pré-simulação. Usando fallback_raw={value} do Gate A/B. Post-Eval={post_score}.`, e retorna `(False, fallback_raw)` (iteração contada como produtiva)

#### Scenario: Circuit breaker dispara sem gates aprovados
- **WHEN** `_check_iteration_abort()` retorna `True` ou `_remaining_time() <= 0` mas `child.gate_post_eval_score == 0.0` (candidato não passou por ambos os gates)
- **THEN** comportamento atual é mantido: retorna `(True, 0.0)`, sem checkpoint, sem backpropagation

#### Scenario: Cenário concreto do log — `condicionais_de_execução` não é perdido
- **WHEN** candidato `condicionais_de_execução` tem Gate A/B score=0.374, Post-Eval score=0.525, e o circuit breaker dispara após `[Checkpoint Incremental] Post-Eval aprovado` mas antes de `simulation()`
- **THEN** `[Gate Fallback] Circuit breaker pré-simulação` é logado, `child.raw_reward = 0.374`, o ITER mostra `raw=0.374` (não `0.000`), o checkpoint é salvo, e a guarda anti-regressão compara `0.374` contra a raiz

### Requirement: Normalização de Schema (Hyphen → Underscore) no Parser DSPy
O sistema SHALL normalizar nomes de campos com hífen para underscore na resposta JSON do LLM antes do parse pelo DSPy, evitando que avaliações bem-sucedidas sejam descartadas por incompatibilidade trivial de nomenclatura.

#### Scenario: LLM retorna `nota_anti-fragilidade` (com hífen)
- **WHEN** o LLM retorna JSON com chave `"nota_anti-fragilidade": 98` (hífen) e o Signature espera `nota_anti_fragilidade` (underscore)
- **THEN** a camada de normalização converte a chave para `"nota_anti_fragilidade"` antes do DSPy parsear, o parse é bem-sucedido, a avaliação produz reward > 0, e o log declara `[Schema Normalization] Chave 'nota_anti-fragilidade' normalizada para 'nota_anti_fragilidade'`

#### Scenario: LLM retorna todas as chaves com underscore (comportamento normal)
- **WHEN** o LLM retorna JSON com todas as chaves já usando underscore
- **THEN** a camada de normalização não altera nada (operação no-op), sem log adicional

### Requirement: Instrução Anti-Hífen nos Descritores dos OutputField
O sistema SHALL incluir instrução explícita nos descritores dos `OutputField` das Signatures de avaliação para que o LLM use underscore (`_`) em vez de hífen (`-`) nos nomes dos campos.

#### Scenario: Prompt inclui instrução anti-hífen
- **WHEN** o prompt é construído a partir dos `OutputField` com `desc`
- **THEN** os descritores dos campos `nota_clareza`, `nota_formatacao`, `nota_robustez`, `nota_densidade_informacional`, `nota_acionabilidade`, `nota_anti_fragilidade` incluem `(use underscore '_' not hyphen '-' in field names)` como sufixo

## MODIFIED Requirements

### Requirement: Ordem de Operações em `_run_mcts_iteration` (Ampliada)
A ordem estabelecida em `fix-checkpoint-race-condition` e `fix-incremental-gate-checkpoint` é ampliada:

1. Selection + Expansion (já existente)
2. Time-gate preventivo (já existente)
3. Gate A/B + Post-Eval (dentro de `_expand_node`, já existente)
4. Checkpoint provisório se ambos os gates aprovaram (já existente)
5. **`_check_iteration_abort()` + `_remaining_time()`: se disparar E `gate_post_eval_score > 0`, aplicar Gate Fallback estendido (NOVO)**
6. Simulação com `future.result(timeout=remaining)`
7. Se `TimeoutError`: Gate Fallback existente (já existente)
8. `_commit_iteration` + `_save_checkpoint`

## REMOVED Requirements
(Nenhum requisito removido nesta fase)
