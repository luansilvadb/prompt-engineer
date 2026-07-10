# Requirements: Skill Optimizer

**Defined:** 2026-07-10
**Core Value:** Otimização de prompts guiada por MCTS com um mecanismo de avaliação que efetivamente valide o comportamento da skill, garantindo código sustentável e modular.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Densificação Cognitiva

- [ ] **COGN-01**: Mutador Cognitivo injeta estruturas de raciocínio lógico (ex: blocos pydantic) nas skills criadas durante a mutação.
- [ ] **COGN-02**: Avaliador de Profundidade calcula a similaridade semântica da resposta para penalizar repetição superficial do prompt original.
- [ ] **COGN-03**: Avaliador de Profundidade utiliza heurísticas lexicais em tempo real para penalizar "verbosidade oca" e recompensar densidade.
- [ ] **COGN-04**: Algoritmo de mutação recompensa instruções comprimidas e altamente lógicas (Densificação Extrema) sobre simples chain-of-thought extenso.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Protocolos Avançados

- **PROT-01**: Suporte configurável para injeção de protocolos de raciocínio específicos como Tree of Thoughts ou Graph of Thoughts.
- **PROT-02**: Seleção dinâmica de estratégia de mutação pelo MCTS baseado no estado do nó.

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Modificação da lógica core do MCTS | O objetivo é focar nas mutações e no juiz, não quebrar a busca que já funciona. |
| Quebra de contratos da API (endpoints) | Clientes dependentes da API devem continuar operando sem disrupção. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| COGN-01 | Phase [N] | Pending |
| COGN-02 | Phase [N] | Pending |
| COGN-03 | Phase [N] | Pending |
| COGN-04 | Phase [N] | Pending |

**Coverage:**
- v1 requirements: 4 total
- Mapped to phases: 0
- Unmapped: 4 ⚠️

---
*Requirements defined: 2026-07-10*
*Last updated: 2026-07-10 after initial definition*
