# Phase 05: Avaliador de Profundidade Heurística - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Penalização em tempo real de "verbosidade oca" utilizando métricas lexicais (`textstat`) para impactar a avaliação da árvore do MCTS.

</domain>

<decisions>
## Implementation Decisions

### Ação no MCTS
- **D-01:** A estratégia de penalização atua em duas camadas: casos extremos sofrem poda imediata na árvore de busca (hard prune), enquanto os demais casos sofrem redução progressiva na nota (multiplicador de penalidade), preservando caminhos com potencial evolutivo.

### Métricas do Textstat
- **D-02:** Utiliza-se uma abordagem combinada. A Densidade Lexical age como o filtro inicial de poda rápida. Nós que sobrevivem a esse filtro são avaliados por uma fórmula combinada (ex: Flesch-Kincaid e outras) para o decaimento progressivo da pontuação.

### Ordem de Avaliação
- **D-03:** As heurísticas lexicais atuam de forma sequencial como filtro primário. Os cálculos do `textstat` rodam ANTES da avaliação pesada. Apenas se o nó passar nesse filtro primário é que as chamadas ao LLM e ao `sentence-transformers` são feitas, as quais podem ocorrer em paralelo para maior eficiência.

### The Agent's Discretion
Nenhuma.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

- `.planning/PROJECT.md` — Project context and core constraints ("Tolerância a Regressões").
- `.planning/ROADMAP.md` — Phase 05 success criteria.
- `.planning/REQUIREMENTS.md` — COGN-03 Requirement definitions.
- `.planning/codebase/ARCHITECTURE.md` — Arquitetura de MCTS, Gateway LiteLLM e FastAPI.
- `.planning/codebase/INTEGRATIONS.md` — Overview de integrações.
- `.planning/codebase/STACK.md` — Principais dependências.
- `.planning/phases/04-avaliador-de-profundidade-sem-ntica/04-CONTEXT.md` — Contexto da fase anterior.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `optimizer.py`: Modificar a lógica do pipeline de recompensa do MCTS para incluir as chamadas às heurísticas (`textstat`).

### Established Patterns
- MCTS reward flow: Pipeline de avaliação. 

### Integration Points
- A integração deve atuar interceptando a geração antes da chamada ao `AvaliadorModoB` (LLM) e do sentence-transformers.

</code_context>

<specifics>
## Specific Ideas
Nenhuma ideia específica capturada fora das decisões.
</specifics>

<deferred>
## Deferred Ideas
Nenhuma - a discussão se manteve no escopo.
</deferred>

---

*Phase: 05-avaliador-de-profundidade-heur-stica*
*Context gathered: 2026-07-10*
