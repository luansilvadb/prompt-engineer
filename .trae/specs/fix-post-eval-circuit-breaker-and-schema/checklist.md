# Checklist

## Gate Fallback para Circuit Breaker Pré-Simulação
- [x] `_check_iteration_abort()` (linha ~1490): quando retorna `True` E `child.gate_post_eval_score > 0`, aplica Gate Fallback em vez de `return True, 0.0`
- [x] `_remaining_time() <= 0` (linhas ~1495): quando dispara E `child.gate_post_eval_score > 0`, aplica Gate Fallback em vez de `return True, 0.0`
- [x] Log emitido: `[Gate Fallback] Circuit breaker pré-simulação. Usando fallback_raw={value} do Gate A/B (A/B={ab_score:.3f}). Post-Eval={post_score:.3f}`
- [x] Log é **diferente** do log de fallback por timeout (`[Gate Fallback] Simulação timeout.`)
- [x] `child.raw_reward = child.gate_ab_score` é definido
- [x] `_commit_iteration(child, fallback_raw, ...)` é chamado
- [x] `_save_checkpoint(child, fallback_raw)` é chamado
- [x] Retorno é `(False, fallback_raw)` — iteração conta como produtiva
- [x] Quando `gate_post_eval_score == 0.0`, comportamento atual é mantido: `return True, 0.0`
- [x] Lógica de Gate Fallback está extraída em método `_apply_gate_fallback(child, reason, heuristic_result)` sem duplicação

## Cenário End-to-End: `condicionais_de_execução` Não É Perdido
- [x] Com Gate A/B score=0.374, Post-Eval score=0.525, circuit breaker disparando após checkpoint incremental:
  - [x] `[Gate Fallback] Circuit breaker pré-simulação` aparece no log (não `[Circuit Breaker] Sem tempo restante`)
  - [x] `[ITER]` mostra `raw=0.374` (não `0.000`)
  - [x] Checkpoint é salvo com `raw=0.374`
  - [x] `_commit_iteration` executa, atualizando bandit e experience store
  - [x] Guarda anti-regressão compara `0.374` contra `root.raw_reward`

## Normalização de Schema (Hyphen → Underscore)
- [x] Função `_normalize_json_keys(text: str) -> str` existe e converte hífens em underscores em chaves JSON
- [x] `"nota_anti-fragilidade": 98` é normalizado para `"nota_anti_fragilidade": 98`
- [x] Múltiplas chaves com hífen são todas normalizadas (ex.: `nota-clareza`, `nota-formatacao`, etc.)
- [x] Chaves já com underscore não são alteradas (no-op)
- [x] A normalização é aplicada na resposta bruta do LLM **antes** do DSPy parsear (no `DSPyAvaliadorModoB.__init__` via `NormalizingLM`)
- [x] Log `[NormalizingLM] Chaves JSON com hífen foram normalizadas` é emitido apenas quando normalização ocorre
- [x] O log **não** é emitido quando nenhuma normalização é necessária (sem ruído)

## Instrução Anti-Hífen nos OutputField
- [x] `AvaliadorDeSkillSignature`: todos os 6 campos de nota têm `(use underscore '_' not hyphen '-' in field names)` no `desc`
- [x] `AvaliadorModoBSignature`: todos os 6 campos de nota têm `(use underscore '_' not hyphen '-' in field names)` no `desc`

## Cenário End-to-End: Avaliação com Hífen Não É Descartada
- [x] LLM retorna `nota_anti-fragilidade: 98` (com hífen) em vez de `nota_anti_fragilidade`
  - [x] `[NormalizingLM]` é logado com a chave normalizada
  - [x] Parse DSPy é bem-sucedido (testado via `_normalize_json_keys` unitário)
  - [x] `reward > 0` (não `0.00`)
  - [x] O conteúdo da avaliação (notas 95-99) é preservado no pipeline

## Testes
- [x] `test_optimizer.py` passa sem regressões (21/21: 18 existentes + 3 novos)
- [x] `test_dspy_signatures.py` passa sem regressões (7/7: 2 existentes + 5 novos)
- [x] `test_mcts.py` passa sem regressões (6/6)
- [x] `test_bandit.py` passa sem regressões (27/28 — 1 falha pré-existente em `test_select_syncs_new_registry_keys_before_choosing`, não relacionada a esta spec)
- [x] `test_optimizer_integration.py` passa sem regressões (4/4)
- [x] Novo teste: Gate Fallback pré-simulação via `_check_iteration_abort()` com `gate_post_eval_score > 0` aplica fallback
- [x] Novo teste: Gate Fallback pré-simulação via `_remaining_time() <= 0` com `gate_post_eval_score > 0` aplica fallback
- [x] Novo teste: Gate Fallback NÃO aplica com `gate_post_eval_score == 0.0` no abort pré-simulação
- [x] Novo teste: `_normalize_json_keys` converte hífen para underscore
- [x] Novo teste: `_normalize_json_keys` é no-op para chaves com underscore
- [x] Novo teste: `_normalize_json_keys` normaliza múltiplas chaves
- [x] Novo teste: `_normalize_json_keys` preserva valores e estrutura
- [x] Novo teste: OutputField desc contém instrução anti-hífen
