# Laudo de Cobertura de Testes

**Data:** 2026-07-12  
**Cobertura global:** 76% (2436 statements, 580 missed)  
**Taxa de sucesso:** 96.5% (139/144 testes passaram)

---

## ❌ MÓDULOS COM COBERTURA CRÍTICA (<70%)

### 1. **src/teleprompter.py** - 14.4% 🔴
**Statements:** 97 total, 83 não testados  
**Impacto:** CRÍTICO - recompilação de juiz sem validação

**Funções não testadas:**
- `_evaluate_drift_gate` (B=10) - pipeline completo de drift
- `_build_trainset` (B=7) - construção de trainset
- `compilar_avaliador` (A=4) - endpoint de compilação

**Risco:**
- Deploy de juiz com drift sem detecção
- Golden set corrupto não detectado
- Fail-open/fail-closed não validados

---

### 2. **src/ausculta_modo_b.py** - 18.0% 🔴
**Statements:** 50 total, 41 não testados  
**Impacto:** CRÍTICO - validação de regras estruturais não testada

**Funções não testadas:**
- `auscultar_modo_b` (B=6) - validação completa de skill

**Risco:**
- Regras críticas não verificadas
- Falsos positivos/negativos em avaliação

---

### 3. **src/config.py** - 25.5% 🔴
**Statements:** 47 total, 35 não testados  
**Impacto:** ALTO - configurações de MCTS não validadas

**Funções não testadas:**
- `setup` (A=5) - inicialização do DSPy
- `_resolve_model_name` (B=7) - resolução de aliases
- `get_mcts_config` (A=1) - carregamento de config

**Risco:**
- Configuração incorreta não detectada
- Model alias inválido causa crash em runtime

---

### 4. **src/routers/jobs.py** - 52.5% 🟡
**Statements:** 183 total, 87 não testados  
**Impacto:** MÉDIO - endpoints de API parcialmente testados

**Endpoints não testados:**
- `train_judge` (B=6) - compilação via API
- `check_drift` (A=2) - verificação de drift
- `stream_progress` (A=4) - SSE streaming
- `_live_event_generator` (B=10) - geração de eventos

**Risco:**
- Timeout de SSE não validado
- Erro de compilação não tratado

---

### 5. **src/mutation_strategies/api.py** - 60.0% 🟡
**Statements:** 5 total, 2 não testados  
**Impacto:** BAIXO - módulo simples

**Funções não testadas:**
- `get_mutation_prompt` (A=1)
- `get_strategy_description` (A=1)

---

### 6. **src/drift/golden.py** - 61.7% 🟡
**Statements:** 60 total, 23 não testados  
**Impacto:** MÉDIO - persistência de golden set

**Funções não testadas:**
- `_restore_frozen_golden` (A=5) - rollback de golden
- `_load` (A=4) - carregamento de JSON
- `save` (A=2) - persistência

**Risco:**
- Corrupção de golden set não recuperada
- Rollback falha silenciosamente

---

### 7. **src/infrastructure/dspy_impl.py** - 63.9% 🟡
**Statements:** 122 total, 44 não testados  
**Impacto:** MÉDIO - agentes DSPy parcialmente testados

**Funções não testadas:**
- `load_avaliador` (A=5) - carregamento de juiz compilado
- `_invoke_judge_modo_b_with` (B=7) - invocação de juiz
- `DSPyAvaliadorModoB.__call__` (B=7) - avaliação modo B

**Risco:**
- Juiz compilado corrompido não detectado
- Erro de parsing de resposta não tratado

---

### 8. **src/optimizer.py** - 66.2% 🟡
**Statements:** 331 total, 112 não testados  
**Impacto:** MÉDIO - lógica de otimização principal

**Funções não testadas:**
- `_log_bandit_stats` (A=3) - logging de estatísticas
- `_select_and_log_best_node` (A=2) - seleção final
- `optimize` (A=4) - loop principal

**Risco:**
- Melhor nó não selecionado corretamente
- Estatísticas de bandit incorretas

---

## 📊 MÓDULOS COM COBERTURA EXCELENTE (≥95%)

✅ **100%:**
- `src/density_evaluator.py`
- `src/heuristic_evaluator.py`
- `src/semantic_evaluator.py`
- `src/domain/mcts.py`
- `src/value_estimator.py`
- `src/domain/agent_interfaces.py`
- `src/domain/store_interfaces.py`
- `src/domain/ausculta_interfaces.py`

✅ **≥95%:**
- `src/ausculta.py` (98%)
- `src/drift/metrics.py` (99%)
- `src/domain/events.py` (96%)
- `src/drift/models.py` (95%)
- `src/experience_store.py` (94%)

---

## 🔍 ANÁLISE DE LACUNAS

### **Padrões de código não testado:**

1. **Tratamento de erro de I/O:**
   - Carregamento de JSON corrompido
   - Falha de escrita em disco
   - Rollback de backup

2. **Casos de borda assíncronos:**
   - Timeout de SSE
   - Cancelamento durante I/O
   - Condições de corrida

3. **Caminhos de configuração:**
   - Variáveis de ambiente ausentes
   - Aliases de modelo inválidos
   - Thresholds fora de range

4. **Integração DSPy:**
   - Respostas mal formatadas
   - Timeout de LLM
   - Parsing de raciocínio estruturado

---

## 📈 EVOLUÇÃO DESEJÁVEL

| Módulo | Atual | Meta Q3 2026 |
|--------|-------|--------------|
| `teleprompter.py` | 14% | 75% |
| `ausculta_modo_b.py` | 18% | 80% |
| `config.py` | 26% | 70% |
| `routers/jobs.py` | 53% | 75% |
| `drift/golden.py` | 62% | 85% |
| `infrastructure/dspy_impl.py` | 64% | 80% |
| `optimizer.py` | 66% | 85% |

**Meta global:** 85% (de 76% atual)

---

## ⚠️ IMPACTO NA QUALIDADE

### **Riscos atuais:**

1. **Drift silencioso:** Golden set pode ser corrompido sem detecção
2. **Configuração incorreta:** Setup pode falhar em produção sem teste
3. **Regressão em avaliação:** Modo B não valida regras estruturais
4. **SSE timeout:** Streaming pode travar sem tratamento

### **Gaps de validação:**

- ❌ Nenhum teste para `compilar_avaliador` (entrypoint crítico)
- ❌ Nenhum teste para `_evaluate_drift_gate` (gate de qualidade)
- ❌ Nenhum teste para `auscultar_modo_b` (validação de regras)
- ❌ Nenhum teste para `train_judge` (endpoint de compilação)

---

## 🔧 AÇÃO REQUERIDA

### **Prioridade ALTA (P0):**
1. ✅ Criar testes para `teleprompter.py::_evaluate_drift_gate`
2. ✅ Criar testes para `ausculta_modo_b.py::auscultar_modo_b`
3. ✅ Criar testes para `config.py::setup` e `_resolve_model_name`

### **Prioridade MÉDIA (P1):**
4. ✅ Criar testes para `routers/jobs.py::train_judge` e `stream_progress`
5. ✅ Criar testes para `drift/golden.py::save` e `_restore_frozen_golden`
6. ✅ Criar testes para `infrastructure/dspy_impl.py::load_avaliador`

### **Prioridade BAIXA (P2):**
7. ✅ Aumentar cobertura de `optimizer.py` para 85%
8. ✅ Adicionar testes de integração para pipeline completo

---

## 📋 RESUMO EXECUTIVO

| Métrica | Valor | Meta |
|---------|-------|------|
| Cobertura global | 76% | 85% |
| Módulos críticos (<70%) | 8 | 0 |
| Linhas não testadas | 580 | <400 |
| Testes falhando | 5 | 0 |

**Veredicto:** ⚠️ **COBERTURA INSUFICIENTE EM MÓDULOS CRÍTICOS**

**Bloqueadores:**
- ❌ `teleprompter.py` (14%) - deploy de juiz sem validação
- ❌ `ausculta_modo_b.py` (18%) - regras estruturais não testadas
- ❌ `config.py` (26%) - configuração não validada

**Ação:** Gerar testes para módulos críticos antes de commit.
