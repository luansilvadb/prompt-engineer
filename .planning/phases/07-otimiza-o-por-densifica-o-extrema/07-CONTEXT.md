# Phase 07: Otimização por Densificação Extrema - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Modificar a função de recompensa do MCTS para recompensar instruções comprimidas e altamente lógicas sobre chain-of-thought extenso, implementando um multiplicador de densidade que boosta scores de outputs concisos e penaliza verbosidade oca.

Cobre o requirement COGN-04: "Algoritmo de mutação recompensa instruções comprimidas e altamente lógicas (Densificação Extrema) sobre simples chain-of-thought extenso."

</domain>

<decisions>
## Implementation Decisions

### Fórmula da Recompensa
- **D-01:** A recompensa por densidade extrema atua como **multiplicador final** no score consolidado do MCTS. O fluxo permanece: `textstat → sentence-transformers → ModoB → densidade(multiplicador) → score final`. A densidade é o último passo, multiplicando o score que já passou por todas as validações.
- **D-02:** Os parâmetros do multiplicador de densidade (ex: `DENSITY_MULTIPLIER_MIN`, `DENSITY_MULTIPLIER_MAX`, `DENSITY_THRESHOLD`) são configuráveis via `config.py`, seguindo o padrão do projeto.

### Métrica de Densidade
- **D-03:** Abordagem **composta em 2 camadas**:
  1. **Universal (toda estratégia):** Taxa de compressão — `len(instrução_gerada) / len(instrução_pai)`. Instruções mais comprimidas que a original recebem boost.
  2. **Bônus (MutadorCognitivo):** Se a instrução contém campos estruturados do `MutadorCognitivoAgent` (`raciocinio_estruturado` com `premissas`, `deducoes`, `conclusao` preenchidos de forma concisa), ganha bônus adicional de densidade.

### Ponto de Integração no Pipeline
- **D-04:** O cálculo de densidade é o **passo final** no pipeline de avaliação, executado após o `AvaliadorModoB`. O multiplicador resultante é aplicado ao score consolidado. Sem refatoração nas camadas existentes.

### Escopo de Aplicação
- **D-05:** A recompensa por densidade se aplica a **todas as estratégias de mutação**. A taxa de compressão universal funciona em qualquer output. O bônus estruturado é aplicado condicionalmente quando os campos do `MutadorCognitivoAgent` estão presentes.

### The Agent's Discretion
Nenhuma — todas as decisões foram explicitadas pelo usuário.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planejamento e Arquitetura
- `.planning/PROJECT.md` — Visão geral, constraints, milestone v1.1 Densificação Cognitiva.
- `.planning/ROADMAP.md` — Phase 07 success criteria (COGN-04).
- `.planning/REQUIREMENTS.md` — Definição de COGN-04.
- `.planning/codebase/ARCHITECTURE.md` — Arquitetura MCTS, pipeline de avaliação, fluxo de recompensa.
- `.planning/codebase/STACK.md` — Dependências principais (DSPy, LiteLLM, sentence-transformers).
- `.planning/codebase/INTEGRATIONS.md` — Overview de integrações.

### Contexto de Fases Anteriores
- `.planning/phases/06-mutador-cognitivo/06-CONTEXT.md` — Contexto do MutadorCognitivo: D-01 (nova Signature), D-02 (raciocinio_estruturado com campos obrigatórios), D-03 (registro hardcoded no StrategyRegistry), D-04 (prior boosting no bandit). A densificação extrema opera SOBRE os outputs do MutadorCognitivo e demais estratégias.
- `.planning/phases/05-avaliador-de-profundidade-heur-stica/05-CONTEXT.md` — Pipeline de avaliação em 3 camadas: textstat (filtro primário) → sentence-transformers → ModoB.
- `.planning/phases/04-avaliador-de-profundidade-sem-ntica/04-CONTEXT.md` — Padrão singleton para modelos pesados, penalidade por similaridade semântica com decaimento contínuo.

### Arquivos de Código Críticos
- `src/optimizer.py` — Onde a função de recompensa do MCTS reside e onde o multiplicador de densidade deve ser injetado como passo final.
- `src/config.py` — Onde os parâmetros de densidade (`DENSITY_MULTIPLIER_MIN`, `DENSITY_MULTIPLIER_MAX`, `DENSITY_THRESHOLD`) devem ser adicionados.
- `src/signatures.py` — Contém `SelfReflectiveAgent` e o `MutadorCognitivoAgent` com seu validador Pydantic (referência para detectar campos estruturados).
- `src/mutation_strategies/bandit.py` — `MutationBandit` e `load_priors()` (já configurado com prior boosting do MutadorCognitivo).
- `src/mutation_strategies/registry.py` — `StrategyRegistry` com as estratégias de mutação registradas.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/optimizer.py`: Função de recompensa do MCTS — ponto de injeção para o multiplicador de densidade como passo final.
- `src/config.py`: Padrão de parâmetros configuráveis via `os.environ` — template para adicionar `DENSITY_*` vars.
- `src/mutation_strategies/`: Estratégias de mutação registradas no `StrategyRegistry`. Cada estratégia gera `nova_instrucao` que pode ser comparada com a instrução pai para taxa de compressão.

### Established Patterns
- Pipeline de avaliação sequencial: textstat → sentence-transformers → ModoB (definido na Fase 5).
- Multiplicadores e penalidades configuráveis via `config.py` (ex: `MCTS_GAMMA`, `MCTS_C_PARAM`, `DRIFT_SPEARMAN_FLOOR`).
- DSPy Signatures com Pydantic validators em `signatures.py` — padrão para detectar campos estruturados no output.

### Integration Points
- `src/optimizer.py`: Função de recompensa — adicionar cálculo de densidade após o `AvaliadorModoB` e antes do retorno do score final.
- `src/config.py`: Adicionar constantes de configuração para os parâmetros do multiplicador de densidade.
- `src/signatures.py`: Se necessário, estender o validador do `MutadorCognitivoAgent` para expor metadata sobre os campos preenchidos (para o bônus estruturado).

</code_context>

<specifics>
## Specific Ideas

- O multiplicador de densidade deve operar em uma faixa configurável (ex: 0.5 a 1.5), onde < 1.0 penaliza verbosidade e > 1.0 recompensa densidade.
- A taxa de compressão ideal deve ser determinada empiricamente — o planner pode definir valores iniciais para `DENSITY_THRESHOLD`.
- O bônus estruturado pode ser implementado como um check de presença/qualidade dos campos `premissas`, `deducoes`, `conclusao` no `raciocinio_estruturado`.

</specifics>

<deferred>
## Deferred Ideas

Nenhuma — a discussão se manteve no escopo da fase.

</deferred>

---

*Phase: 07-Otimização por Densificação Extrema*
*Context gathered: 2026-07-10*
