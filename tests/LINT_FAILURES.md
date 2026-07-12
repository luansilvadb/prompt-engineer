# Laudo de Falhas de Linter

**Data:** 2026-07-12  
**Critério:** Código-fonte não conforme com regras de estilo e importações

---

## ❌ FALHAS CRÍTICAS DETECTADAS

### 1. **src/domain/job_interfaces.py:3**
- **Regra:** F401 (unused-import)
- **Problema:** `dataclasses.field` importado mas não utilizado
- **Impacto:** Poluição do namespace, falso positivo em análise de dependências

### 2. **src/optimizer.py:19**
- **Regra:** F401 (unused-import)
- **Problema:** `typing.Callable` e `typing.Optional` importados mas não utilizados
- **Impacto:** Redundância, confusão sobre API real do módulo

### 3. **src/optimizer.py:27**
- **Regra:** F401 (unused-import)
- **Problema:** `src.domain.config.load_mcts_config` importado mas não utilizado
- **Impacto:** Falsa dependência, dificulta refatoração

### 4. **src/optimizer.py:28**
- **Regra:** F401 (unused-import)
- **Problema:** `EventLevel` e `NodeEventPayload` importados mas não utilizados
- **Impacto:** Namespace poluído, dificulta leitura

### 5. **src/optimizer.py:37**
- **Regra:** F401 (unused-import)
- **Problema:** `MutationBandit`, `get_mutation_prompt`, `registry` importados mas não utilizados
- **Impacto:** Código morto, confusão sobre dependências reais

### 6. **tests/test_optimizer.py:32-33**
- **Regra:** F821 (undefined-name)
- **Problema:** `mock_heavy_evaluators` referenciado mas não definido
- **Impacto:** **TESTE QUEBRADO** - impossível executar corretamente

---

## 📊 RESUMO

| Categoria | Quantidade |
|-----------|------------|
| Importações não utilizadas | 9 |
| Nomes indefinidos | 2 |
| **Total de violações** | **11** |

---

## ⚠️ IMPACTO NA QUALIDADE

1. **Testes quebrados:** 1 teste (`test_optimizer_layer1_hard_pruning`) falha por referência indefinida
2. **Manutenibilidade:** Importações fantasma dificultam refatoração e análise de impacto
3. **Performance:** Importações desnecessárias aumentam tempo de carregamento do módulo

---

## 🔧 AÇÃO REQUERIDA

**Passar para `/code --fix`** com descrição:
> "Importações não utilizadas em src/optimizer.py e src/domain/job_interfaces.py; variável mock_heavy_evaluators indefinida em tests/test_optimizer.py"
