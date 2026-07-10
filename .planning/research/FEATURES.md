# Feature Research

**Domain:** Prompt Optimization (Teleprompter) - Cognitive Densification
**Researched:** 2026-07-10
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Mutador Cognitivo** (Reasoning Injection) | To densify skills, the system must inject explicit reasoning protocols (like Chain of Thought or advanced logical steps) during mutations. | MEDIUM | Relies on the existing clean mutation architecture created in v1.0. |
| **Avaliador de Profundidade** (Shallow Reasoning Penalty) | If reasoning is injected, the judge must be capable of verifying its depth and penalizing superficial or weak logic. | HIGH | Expands the "Juiz Modo B" (defect-hunting mode) validated in v1.0. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Densificação Cognitiva** | Creates prompts that force the LLM into a highly compressed, rigorous logical reasoning state, rather than just verbose CoT. Supercharges normal capacities efficiently. | HIGH | This is the core goal of v1.1 and the main differentiator against generic prompt optimizers. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Changing MCTS Core Logic** | To potentially speed up the search process with new reasoning nodes. | Out of scope for this milestone. Risks breaking the core algorithm that already works well. | Focus strictly on new *mutators* and *judge extensions* while keeping the MCTS search algorithm intact. |
| **Breaking API Contracts** | To expose new cognitive tuning parameters to external users. | Breaks backward compatibility for clients/UIs relying on the current endpoints. | Implement the Mutador and Avaliador internally as part of the default pipeline, completely transparent to API consumers. |

## Feature Dependencies

```
[Mutador Cognitivo]
    └──requires──> [Arquitetura limpa de mutações (v1.0)]

[Avaliador de Profundidade]
    └──requires──> [Juiz Modo B (v1.0)]

[Mutador Cognitivo] ──enhances──> [MCTS Optimizer]
[Avaliador de Profundidade] ──enhances──> [MCTS Optimizer]
```

### Dependency Notes

- **[Mutador Cognitivo] requires [Arquitetura limpa de mutações (v1.0)]:** The new mutator leverages the refactored and well-delineated `src/mutation_strategies/` subpackage.
- **[Avaliador de Profundidade] requires [Juiz Modo B (v1.0)]:** The new depth evaluator builds on top of the strict, defect-hunting logic established in Modo B, extending it from structural defects to logical/reasoning defects.
- **Both enhance [MCTS Optimizer]:** They provide better candidates (Mutador) and better reward signals (Avaliador) to the existing MCTS loop.

## MVP Definition

### Launch With (v1.1)

Minimum viable product — what's needed to validate the concept.

- [x] **Mutador Cognitivo** — Essential for generating candidates with advanced reasoning protocols.
- [x] **Avaliador de Profundidade** — Essential for preventing regressions and ensuring the reasoning is actually deep and not just aesthetic.

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] **Custom Cognitive Protocols** — Allow configuring which specific reasoning protocols to inject (e.g., ToT, GoT) once the base cognitive mutator is validated.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **Dynamic Strategy Selection** — MCTS dynamically picking which mutation strategy (structural vs cognitive) to apply based on node state.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Mutador Cognitivo | HIGH | MEDIUM | P1 |
| Avaliador de Profundidade | HIGH | HIGH | P1 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Generic Optimizers (e.g., DSPy basic) | Competitor B | Our Approach |
|---------|---------------------------------------|--------------|--------------|
| Reasoning Optimization | Rely on basic few-shot or simple CoT bootstrapping. | N/A | **Densificação Cognitiva**: Explicit injection of advanced reasoning protocols and rigorous penalization of shallow logic via MCTS. |

## Sources

- `.planning/PROJECT.md` (Current Milestone: v1.1 Densificação Cognitiva)

---
*Feature research for: Prompt Optimization (Teleprompter) - Cognitive Densification*
*Researched: 2026-07-10*
