# Phase 4: Avaliador de Profundidade Semântica - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Calcular similaridade semântica para penalizar repetição superficial usando `sentence-transformers` na recompensa do MCTS.

</domain>

<decisions>
## Implementation Decisions

### Modelo de Embedding
- **D-01:** Utilizar `paraphrase-multilingual-MiniLM-L12-v2` para suporte multilíngue (focado na precisão semântica para os prompts em português do Modo B).

### Forma de Penalidade
- **D-02:** Decaimento contínuo (penalização progressiva) a partir de um limite alto (> 0.85). Evitar limites duros para manter o MCTS estável.

### Integração no Pipeline
- **D-03:** A integração deve atuar como um passo separado na função de recompensa do MCTS (`optimizer.py`), mantendo responsabilidades separadas em relação ao `AvaliadorModoB` via LLM (focado em matemática e penalização final).

### Ciclo de Vida do Modelo
- **D-04:** Instanciar o `sentence-transformers` globalmente na memória no startup (no escopo do módulo/singleton) para minimizar o overhead das requisições via FastAPI.

### The Agent's Discretion
Nenhuma.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planejamento e Arquitetura
- `.planning/PROJECT.md` — Visão geral e Constraints ("Isolamento de Estado", "Tolerância a Regressões").
- `.planning/ROADMAP.md` — Definição das fases e critérios de sucesso.
- `.planning/codebase/ARCHITECTURE.md` — Arquitetura de MCTS, Gateway LiteLLM e FastAPI.
- `.planning/codebase/INTEGRATIONS.md` — Overview de integrações (LiteLLM, DSPy).
- `.planning/codebase/STACK.md` — Principais dependências (DSPy, FastAPI, LiteLLM) e configuração (`config.py`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `optimizer.py`: Modificar a função de recompensa do MCTS para incluir o cálculo de penalidade do sentence-transformers.
- `config.py`: Variáveis de configuração e chaves, onde a carga do modelo pode ser inicializada ou referenciada globalmente se necessário.

### Established Patterns
- MCTS reward flow: Já utiliza funções de avaliação combinadas. A similaridade deve multiplicar ou reduzir a nota obtida pelas heurísticas e LLM (AvaliadorModoB).

### Integration Points
- No pipeline do `teleprompter.py`/`optimizer.py` (MCTS evaluation). O cálculo deve ocorrer comparando o nó original/instrução pai com o nó gerado.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-Avaliador de Profundidade Semântica*
*Context gathered: 2026-07-10*
