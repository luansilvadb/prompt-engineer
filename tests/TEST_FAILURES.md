# Laudo de Falhas de Testes — ⚠️ SUPERSEDED (RESOLVIDO)

> **STATUS: SUPERSEDED por `QUALITY_AUDIT_FINAL.md`**  
> Este laudo descrevia 5 falhas ativas em 2026-07-12 (~10:39).  
> Revalidação independente em 2026-07-12 confirma: **todas as 5 foram corrigidas**.  
> Mantido apenas como rastro de auditoria — NÃO representa o estado atual.

**Data original:** 2026-07-12 (~10:39) — **stale**  
**Revalidação independente:** 2026-07-12 — 233/233 passando, ruff limpo, CC máx. 10, cobertura 84%

---

## ✅ RESOLUÇÃO DAS 5 FALHAS (verificação independente)

Comando: `python -m pytest <5 testes> -v` → **5 passed, 0 failed**

| # | Teste | Falha alegada (stale) | Estado real agora | Evidência |
|---|-------|----------------------|-------------------|-----------|
| 1 | `test_optimizer_layer1_hard_pruning` | `NameError: mock_heavy_evaluators` | ✅ **PASS** | Fixture agora existe em `conftest.py`; teste recebe `mock_heavy_evaluators` por parâmetro |
| 2 | `test_density_neutral_at_same_length` | `0.9 == 1.0` (mult. de densidade indevido) | ✅ **PASS** | `density_evaluator.py`: `child_len == parent_len` → retorna `multiplier=base_threshold` neutro (RN-05) |
| 3 | `test_optimizer_mcts_iteration_cancelled` | `should_break is False` | ✅ **PASS** | Cancelamento interrompe a iteração corretamente |
| 4 | `test_optimizer_mcts_iteration_happy_path` | `9.0 == 10.0` (-10% indevido) | ✅ **PASS** | `optimizer.py:415`: `if self.lexical_density_min == 0.0: return reward` (gate desabilitado) |
| 5 | `test_optimizer_mcts_iteration_max_children` | `4.5 == 5.0` (-10% indevido) | ✅ **PASS** | Mesmo gate de RN-05 — densidade neutra quando desabilitada |

### Causa-raiz da divergência (não há defeito atual)
O laudo original foi emitido **antes** da correção do multiplicador de densidade (RN-05:  
retorno neutro quando `lexical_density_min == 0.0` ou comprimentos iguais) e antes da  
criação da fixture `mock_heavy_evaluators`. Após essas correções, todas as 5 falhas  
migraram para verde. O `QUALITY_AUDIT_FINAL.md` registrou a revalidação completa.

---

## 📋 VEREDICTO ATUAL

**Nenhuma falha ativa.** Estado do repositório (verificado independentemente):

- `ruff check src/ tests/` → `All checks passed!`
- `pytest tests/` → **233 passed**
- `radon cc src/` → máx. **B(10)** (≤ limite da skill)
- `pytest --cov=src` → **84%** (411/2561 missed)

**Passagem de bastão:** → `/commit`  
**NÃO acionar** `/code --fix` com base neste laudo — ele está obsoleto.
