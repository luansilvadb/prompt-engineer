# Tasks

## Bug 1: Gate Fallback para Circuit Breaker Pré-Simulação

- [x] Task 1: Estender Gate Fallback para abort pré-simulação em `_run_mcts_iteration`
  - [x] SubTask 1.1: No bloco `if self._check_iteration_abort(): return True, 0.0` (linha ~1450), verificar se `child.gate_post_eval_score > 0` ANTES de retornar. Se sim, executar a lógica de Gate Fallback (mesma do `TimeoutError`) e retornar `(False, fallback_raw)`
  - [x] SubTask 1.2: No bloco `if remaining <= 0:` (linhas ~1454-1457), verificar se `child.gate_post_eval_score > 0` ANTES de retornar `(True, 0.0)`. Se sim, executar a lógica de Gate Fallback e retornar `(False, fallback_raw)`
  - [x] SubTask 1.3: Emitir log distinto para o fallback pré-simulação: `[Gate Fallback] Circuit breaker pré-simulação. Usando fallback_raw={value} do Gate A/B (A/B={ab_score:.3f}). Post-Eval={post_score:.3f}`
  - [x] SubTask 1.4: Extrair a lógica de Gate Fallback para um método privado `_apply_gate_fallback(child, reason: str)` para evitar duplicação (atualmente repetida no `TimeoutError` e nos dois novos pontos de abort)
  - [x] SubTask 1.5: Garantir que `child.gate_post_eval_score` é confiável nos pontos de abort — o checkpoint provisório (linhas ~1442-1448) já foi salvo antes, então `gate_post_eval_score > 0` implica que ambos os gates aprovaram

## Bug 2: Normalização de Schema (Hyphen → Underscore)

- [x] Task 2: Adicionar camada de normalização de chaves no `JudgeModule`
  - [x] SubTask 2.1: Criar uma função utilitária `_normalize_json_keys(text: str) -> str` que identifica chaves JSON com hífen e as converte para underscore (ex.: `"nota_anti-fragilidade"` → `"nota_anti_fragilidade"`). Usar regex para capturar padrões `"chave-com-hifen":` dentro de JSON
  - [x] SubTask 2.2: Em `JudgeModule.__call__` (linha ~229), wrappear a chamada `self._predictor(...)` com um interceptador de LM customizado que aplica `_normalize_json_keys` na resposta bruta do LLM antes do DSPy parsear
  - [x] SubTask 2.3: Emitir log `[Schema Normalization] Chave 'X' normalizada para 'Y'` apenas quando uma normalização de fato ocorrer (para facilitar diagnóstico)
  - [x] SubTask 2.4: Verificar se o DSPy expõe um hook de pós-processamento de resposta (ex.: `adapter`, `lm.configure()`). Se não houver hook nativo, implementar como wrapper no `self._predictor` usando monkey-patch do método `forward` do LM subjacente

- [x] Task 3: Adicionar instrução anti-hífen nos descritores dos OutputField
  - [x] SubTask 3.1: Em `AvaliadorDeSkillSignature` (linhas ~70-77), adicionar `(use underscore '_' not hyphen '-' in field names)` ao final de cada `desc` dos campos: `nota_clareza`, `nota_formatacao`, `nota_robustez`, `nota_densidade_informacional`, `nota_acionabilidade`, `nota_anti_fragilidade`
  - [x] SubTask 3.2: Em `AvaliadorModoBSignature` (linhas ~104-112), aplicar a mesma adição nos mesmos campos

## Testes

- [x] Task 4: Testes de validação
  - [x] SubTask 4.1: Teste unitário do Gate Fallback pré-simulação — simular `_check_iteration_abort() == True` com `child.gate_post_eval_score=0.525`, verificar que `_apply_gate_fallback` é chamado e retorna `(False, fallback_raw)`
  - [x] SubTask 4.2: Teste unitário de que fallback NÃO é aplicado quando `gate_post_eval_score == 0.0` no abort pré-simulação
  - [x] SubTask 4.3: Teste unitário da função `_normalize_json_keys` — entrada com `"nota_anti-fragilidade": 98` deve produzir `"nota_anti_fragilidade": 98`
  - [x] SubTask 4.4: Teste unitário de que `_normalize_json_keys` é no-op quando as chaves já estão com underscore
  - [x] SubTask 4.5: Teste unitário de que `_normalize_json_keys` normaliza múltiplas chaves com hífen simultaneamente
  - [x] SubTask 4.6: Teste unitário de que as descrições dos OutputField contêm a instrução anti-hífen
  - [x] SubTask 4.7: Executar `test_optimizer.py`, `test_mcts.py`, `test_bandit.py`, `test_optimizer_integration.py` e verificar passagem sem regressão

# Task Dependencies
- Task 1 (Gate Fallback pré-simulação) é independente
- Task 2 (normalização de schema) é independente
- Task 3 (instrução anti-hífen) é independente e pode ser feita em paralelo com Task 2
- Task 4 (testes) depende de Tasks 1-3
- Task 1.4 (extrair método `_apply_gate_fallback`) é refatoração interna — as Subtasks 1.1-1.3 podem ser feitas inline primeiro e depois extraídas
