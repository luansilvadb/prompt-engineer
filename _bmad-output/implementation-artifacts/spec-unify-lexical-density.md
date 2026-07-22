---
title: 'Unificar compute_lexical_density — Eliminar Duplicação de Type-Token Ratio'
type: 'refactor'
created: '2026-07-21T23:18:00-03:00'
status: 'done'
review_loop_iteration: 0
baseline_commit: '4a4f57cb1fd356746f34c0431754ed644b59b470'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A type-token ratio (densidade lexical) está reimplementada 3 vezes no codebase. `density_evaluator.py` exporta `compute_lexical_density()` como função canônica, `heuristic_evaluator.py` repete a lógica idêntica inline (linhas 53-56), e `value_estimator.py` tem uma variação inline (linhas 59-62) com tokenizador diferente. Isso causa divergência silenciosa se a fórmula for ajustada e triplica o custo de manutenção.

**Approach:** Fazer `heuristic_evaluator.py` chamar a função canônica `compute_lexical_density` já existente. Para `value_estimator.py`, substituir a lógica inline por `compute_lexical_density` — a pequena diferença de tokenização (`re.findall` com acentos vs `re.sub` + split) não altera a semântica do TTR no domínio de skills textuais.

## Boundaries & Constraints

**Always:** Importar `compute_lexical_density` de `src.density_evaluator`. Manter a assinatura pública existente. Rodar `pytest` após cada alteração. Não alterar comportamento de runtime — TTR deve produzir os mesmos valores numéricos (ou diferença ≤ 0.01).

**Ask First:** Se `pytest` falhar por diferença numérica no value_estimator, reportar antes de ajustar thresholds.

**Never:** Modificar a função canônica `compute_lexical_density`. Alterar `_extract_features` além da linha do TTR. Tocar em `optimizer.py`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| heuristic_evaluator chama canônica | Texto com pontuação | `unique_ratio` idêntico ao valor inline anterior | Se diferente, reverter e reportar |
| value_estimator chama canônica | Texto com acentos (á, ç, ã) | `ttr` com diferença ≤ 0.01 do valor anterior | Se diferença > 0.01, HALT e perguntar |
| Texto vazio | `text = ""` | Retorna 0.0 (canônica já trata) | N/A |

</frozen-after-approval>

## Code Map

- `src/density_evaluator.py:44-49` — função canônica `compute_lexical_density(text: str) -> float`, exportada e importada por optimizer.py
- `src/heuristic_evaluator.py:53-56` — lógica idêntica inline dentro de `evaluate_heuristics`: `re.sub(r'[^\w\s]', '', text.lower())` + split + `len(set)/len`
- `src/value_estimator.py:59-62` — variação inline dentro de `_extract_features`: `re.findall(r'[a-záàâãéêíóôúç]+', text.lower())` + `len(set)/len`
- `src/optimizer.py` — já importa `compute_lexical_density` de density_evaluator

## Tasks & Acceptance

**Execution:**
- [x] `src/heuristic_evaluator.py` — SUBSTITUIR linhas 53-56 (cálculo inline de `unique_ratio`) por chamada a `compute_lexical_density(text)` importada de `src.density_evaluator`
- [x] `src/value_estimator.py` — SUBSTITUIR linhas 59-62 (cálculo inline de `ttr` e `diversity_score`) por `ttr = compute_lexical_density(text)` importada de `src.density_evaluator`

**Acceptance Criteria:**
- Given `heuristic_evaluator.evaluate_heuristics(texto)`, when chamado com qualquer texto, then `unique_ratio` é idêntico ao valor antes da refatoração (mesma fórmula, mesmo regex)
- Given `value_estimator._extract_features(texto)`, when chamado com qualquer texto, then `diversity_score` difere ≤ 0.01 do valor anterior (tokenizador ligeiramente diferente: `re.sub` vs `re.findall`)
- Given o codebase refatorado, when `pytest` roda da raiz, then todos os testes passam sem falhas

## Verification

**Commands:**
- `python -m pytest tests/ -x -q` — expected: todos os testes passam
- `python -c "from src.density_evaluator import compute_lexical_density; from src.heuristic_evaluator import evaluate_heuristics; print('imports OK')"` — expected: imports funcionam sem circularidade

## Suggested Review Order

- Entry point — substituição direta da lógica inline idêntica por chamada canônica, sem delta semântico
  [`heuristic_evaluator.py:55`](../../src/heuristic_evaluator.py#L55)

- Ponto de atenção — tokenizador trocado de `re.findall` (acentos) para `re.sub` + split; spec aceita diferença ≤ 0.01
  [`value_estimator.py:62`](../../src/value_estimator.py#L62)

- Função canônica de referência — confirma que `compute_lexical_density` já existia e não foi alterada
  [`density_evaluator.py:44`](../../src/density_evaluator.py#L44)
