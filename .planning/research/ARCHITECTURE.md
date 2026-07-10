# Architecture Research

**Domain:** Prompt Engineering / Agent Optimizer (v1.1 Densificação Cognitiva)
**Researched:** 2026-07-10
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Optimizer Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────────────┐       ┌────────────────────────┐│
│  │   Mutador Cognitivo    │   →   │Avaliador de Profundidade││
│  │ (Seeded Strategy Pool) │       │     (Juiz Modo B)      ││
│  └────────────────────────┘       └────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Mutador Cognitivo** | Injetar protocolos explícitos de raciocínio (Chain of Thought, Reflection) nas skills geradas, transformando skills estáticas em processos lógicos densos. | Estratégia hard-coded ou pre-seeded injetada via `src/mutation_strategies/registry.py`. |
| **Avaliador de Profundidade** | Penalizar skills que exibem raciocínio raso ou superficial. Expande a capacidade de caça-defeitos para avaliar densidade lógica. | Expansão das signatures `AvaliadorModoB` e `AvaliacaoModoB` em `src/signatures.py`. |

## Recommended Project Structure

Apenas componentes alterados para as novas features (as demais partes de `src/drift/` e MCTS continuam como estão, honrando a restrição "Out of Scope").

```text
src/
├── mutation_strategies/
│   └── registry.py      # [MODIFIED] Adição de lógica para pre-seeding de estratégias vitais (Mutador Cognitivo)
├── signatures.py        # [MODIFIED] Atualização do AvaliadorModoB para suportar Avaliação de Profundidade
└── teleprompter.py      # [INTEGRATION] Ponto de recompilação do Juiz que assimilará as novas regras
```

### Structure Rationale

- **`src/mutation_strategies/registry.py`:** Mantém o desacoplamento de estratégias isolado no pacote de domínio correspondente. O mutador cognitivo será carregado nativamente por aqui para o MCTS/Bandit sem tocar na lógica global.
- **`src/signatures.py`:** Centraliza a modificação do Juiz (Avaliador de Profundidade). A introdução de raciocínio lógico é apenas uma dimensão (ou extensão de dimensão) nova no Modo B, o que valida perfeitamente o seu lugar junto à `AvaliacaoModoB`.

## Architectural Patterns

### Pattern 1: Pre-Seeded Core Strategies

**What:** Adicionar estratégias essenciais (como o Mutador Cognitivo) diretamente no construtor/load do `StrategyRegistry`.
**When to use:** Quando o sistema precisa de heurísticas provadas que garantem densidade sem depender apenas da descoberta aleatória (Tabula Rasa).
**Trade-offs:** Cria uma leve rigidez no registry, mas garante que otimizações chaves sempre entrem na distribuição do Multi-Armed Bandit.

### Pattern 2: Multidimensional Cognitive Judging

**What:** Adição de campos específicos em assinaturas DSPy (`AvaliadorModoB`) para forçar o LLM Juiz a buscar "Raciocínio Raso" antes de dar notas em estética.
**When to use:** Quando o Juiz ("Modo A") se contenta com linguagem bonita que carece de protocolos acionáveis e densos.
**Trade-offs:** Aumenta a latência/token usage da avaliação, mas garante que o otimizador penalize e efetivamente evite "drift cognitivo" (regressões que deixam a skill 'burra').

## Data Flow

### Request Flow (MCTS Iteration Flow)

```text
[MCTS Expansion Node]
    ↓ (Puxa do Bandit)
[Mutador Cognitivo Selecionado] → [SelfReflectiveAgent gera nova skill]
    ↓ (Passa skill para avaliação)
[_invoke_judge_modo_b_with]
    ↓ (Juiz modo B expandido analisa)
[Avaliador de Profundidade detecta Raciocínio Raso como Defeito]
    ↓ 
[funcao_de_recompensa subtrai pontos (penalty)]
    ↓ (Atualiza)
[MCTS Backpropagation]
```

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `registry` ↔ `Bandit` | Dicionário de Estratégias | O registry deve prover o "Mutador Cognitivo" transparentemente ao iterar chaves. |
| `AvaliadorModoB` ↔ `funcao_de_recompensa` | Pydantic Models (`AvaliacaoModoB`) | O campo `defeitos_encontrados` deve explicitar falhas lógicas para escalar a penalidade no reward final. |

## Build Order (Considerando Dependências)

A ordem de build é crítica para não quebrar a compilação do Juiz nem do Otimizador.

1. **`src/signatures.py` (Avaliador de Profundidade):** 
   - Expandir a classe `AvaliadorModoB` para instruir o LLM a julgar "densidade de raciocínio".
   - Ajustar `AvaliacaoModoB` para classificar "raciocínio raso" como defeito no campo `defeitos_encontrados`.
   - Modificar a `funcao_de_recompensa` (se necessário) para aumentar a penalidade para ausência de raciocínio lógico estruturado.
   
2. **`src/mutation_strategies/registry.py` (Mutador Cognitivo):** 
   - Implementar método para carregar estratégias semente (seed) estáticas — injetar o prompt do "Mutador Cognitivo" no pool do registry.

3. **`src/teleprompter.py` (Recompilação):** 
   - Re-rodar as rotinas de compilação do juiz (`compilar_avaliador`) para o DSPy convergir as novas instruções contra o *Golden Set* de testes.
   - Isso garante que a atualização das assinaturas passe pelo crivo de não-regressão comportamental.

---
*Architecture research for: Mutador Cognitivo and Avaliador de Profundidade*
*Researched: 2026-07-10*
