---
title: 'Refatoração da Codebase — Rodada 2: Complexidade Residual e Código Morto'
type: 'refactor'
created: '2026-07-22T01:00:00-03:00'
status: 'done'
review_loop_iteration: 0
baseline_commit: '0b1be6e7ecdef72000ca435e6219975ce53fb35a'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A rodada 1 de refatoração reduziu a complexidade das ~8 funções mais críticas, mas `_run_with_fail_fast` (CC=12) ficou marginalmente acima do target de 10. Além disso, o vulture ainda detecta código morto residual que sobreviveu à primeira limpeza: métodos de interface nunca chamados (`emit_status`), helpers de histórico órfãos (`append_drift_report`), atributos write-only (`_total_selects`), constantes não referenciadas (`SCHEMA_VERSION`), e um arquivo JS de view (`JudgeView.js`) nunca importado pelo entry point do frontend.

**Approach:** Extrair o bloco de safety-net de `_run_with_fail_fast` para um helper `_apply_safety_net`, removendo ~4 branches da função principal. Eliminar os 5 itens de código morto confirmados (verificados contra testes e imports). Remover `JudgeView.js`.

## Boundaries & Constraints

**Always:** Manter assinaturas públicas inalteradas. Rodar `pytest` após cada arquivo modificado. McCabe alvo ≤ 10 por função. Preservar comportamento de runtime idêntico. Cada extração com nome claro e responsabilidade única.

**Ask First:** Se `pytest` falhar. Se a extração criar função com mais de 4 parâmetros.

**Never:** Alterar `pyproject.toml` ou `requirements.txt`. Modificar lógica de negócio, thresholds, ou hiperparâmetros. Remover `_apply_verification_hints` ou `_abort_fail_fast` (testados diretamente). Remover `circuit_breaker`, `get_expansion_order`, `get_level_one_nodes`, `triggered_metric`, `_total_llm_calls` (todos referenciados em testes). Remover variáveis prometheus em `metrics.py` (registradas no REGISTRY do prometheus_client e expostas via `get_metrics()`). Tocar em `src/mutation_strategies/` além de `_total_selects`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Safety-net: probe sem verification_hints | `probe.verification_hints` vazio | `_apply_safety_net` retorna `avaliacao` inalterada | N/A |
| Safety-net: probe com hints, LLM detecta violação | `avaliacao.manteve_regras_criticas=False` | `_apply_safety_net` retorna `avaliacao` inalterada | N/A |
| Safety-net: probe com hints, LLM falha, safety-net confirma | `confirmed=True` + Modo B | Força `manteve_regras_criticas=False`, anexa defeito SafetyNet | N/A |
| Safety-net: probe com hints, LLM falha, safety-net confirma | `confirmed=True` + Modo A | Força `manteve_regras_criticas=False` via `Avaliacao` base | N/A |
| Remoção de emit_status quebra JobEventEmitter | `JobEventEmitter` instanciado sem `emit_status` | `JobEventEmitter` funciona normalmente | `emit_status` nunca foi chamado em produção |

</frozen-after-approval>

## Code Map

- `src/drift/runner.py:127` — `_run_with_fail_fast` (CC=12): safety-net block (linhas 153-184) aninhado em try/except — principal alvo de extração
- `src/domain/events.py:50` — `emit_status` em `IJobEventEmitter`: definido, nunca chamado
- `src/infrastructure/events.py:42` — `emit_status` em `JobEventEmitter`: implementação concreta do método órfão
- `src/drift/history.py:39` — `append_drift_report`: função de persistência nunca chamada
- `src/experience_store_sqlite.py:25` — `SCHEMA_VERSION = 1`: constante nunca referenciada
- `src/mutation_strategies/bandit.py:49` — `_total_selects`: atributo write-only (escrito 3x, nunca lido)
- `frontend/src/views/JudgeView.js` — classe exportada mas nunca importada em `index.js` nem em teste

## Tasks & Acceptance

**Execution:**
- [x] `src/drift/runner.py` — Extrair `_apply_safety_net` de `_run_with_fail_fast` (CC=12→≤10): isolar o bloco safety-net (linhas 153-184) que aplica verificação textual determinística como camada complementar ao LLM
- [x] `src/domain/events.py` — Remover método `emit_status` (linha 50) da interface `IJobEventEmitter`
- [x] `src/infrastructure/events.py` — Remover método `emit_status` (linha 42) da classe `JobEventEmitter`
- [x] `src/drift/history.py` — Remover função `append_drift_report` (linhas 39-63)
- [x] `src/experience_store_sqlite.py` — Remover constante `SCHEMA_VERSION` (linha 25)
- [x] `src/mutation_strategies/bandit.py` — Remover atributo `_total_selects`: eliminar declaração no `__init__` (linha 49) e 3 incrementos (linhas 145, 154, 162)
- [x] `frontend/src/views/JudgeView.js` — Deletar arquivo (classe nunca importada por `index.js`)

**Acceptance Criteria:**
- Given o código refatorado, when `pytest` é executado, then todos os testes passam sem alteração
- Given `_run_with_fail_fast`, when medido com `radon cc -a`, then CC ≤ 10
- Given o código limpo, when `python3 -m vulture src/ --min-confidence 80`, then zero achados (exceto `example`/`trace` — falso positivo do DSPy)
- Given `frontend/src/views/JudgeView.js` removido, when o frontend é carregado, then todas as views operam sem erro de console

## Verification

**Commands:**
- `python3 -m pytest tests/ -q` — expected: todos passam
- `python3 -m radon cc src/drift/runner.py -s` — expected: `_run_with_fail_fast` CC ≤ 10
- `python3 -m vulture src/ --min-confidence 80` — expected: apenas `example` e `trace` (falso positivo DSPy)

## Suggested Review Order

**Safety-net extraction — extrai verificação determinística de `_run_with_fail_fast`**

- Entry point: nova função `_apply_safety_net` com early-returns e dispatch por tipo de avaliação
  [`runner.py:81`](../../src/drift/runner.py#L81)

- Call site: substitui bloco inline de 37 linhas por chamada única ao helper extraído
  [`runner.py:197`](../../src/drift/runner.py#L197)

**Remoção de `emit_status` — método de interface nunca chamado**

- Interface: remove declaração abstrata de `IJobEventEmitter`
  [`events.py:50`](../../src/domain/events.py#L50)

- Implementação: remove método concreto de `JobEventEmitter` que logava `[status]`
  [`events.py:42`](../../src/infrastructure/events.py#L42)

**Remoção de funções e constantes órfãs**

- `append_drift_report` removida; imports `os`, `Optional`, `DriftReport` e constante `MAX_ENTRIES` limpos como efeito colateral
  [`history.py:10`](../../src/drift/history.py#L10)

- `SCHEMA_VERSION = 1` removida — número mágico permanece em `_ensure_schema` (ver deferred-work)
  [`experience_store_sqlite.py:25`](../../src/experience_store_sqlite.py#L25)

- `_total_selects` write-only removido de `MutationBandit.__init__` e 3 call sites em `select()`
  [`bandit.py:49`](../../src/mutation_strategies/bandit.py#L49)

**Frontend cleanup**

- `JudgeView.js` deletado — classe exportada nunca importada por `index.js` nem por testes
  *(arquivo removido, sem link)*
