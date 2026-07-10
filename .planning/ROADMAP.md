# Roadmap: Skill Optimizer

## Milestones

- ✅ **v1.0 Skill Optimizer MVP** — Phases 1-3 (shipped 2026-07-10)
- 🏃 **v1.1 Densificação Cognitiva** — Phases 4-7

## Phases

<details>
<summary>✅ v1.0 Skill Optimizer MVP (Phases 1-3) — SHIPPED 2026-07-10</summary>

- [x] Phase 1: Architectural Cleanup & Densification (5/5 plans) — completed 2026-07-09
- [x] Phase 2: Judge "Caça-Defeitos" Mode (2/2 plans) — completed 2026-07-09
- [x] Phase 3: Close gap: JUD-01, JUD-02 Fix optimizer.py to target Mode B (1/1 plans) — completed 2026-07-09

</details>

### Phase 4: Avaliador de Profundidade Semântica

**Requirement**: COGN-02
**Focus**: Calcular similaridade semântica para penalizar repetição superficial.
**Success Criteria:**

- [ ] System includes `sentence-transformers` integration for calculating cosine similarity between prompt and generated output.
- [ ] MCTS penalizes outputs that exhibit high semantic similarity to the original prompt without adding reasoning.
- [ ] Tests demonstrate correct calculation of distance metrics without causing test suite timeout.

### Phase 5: Avaliador de Profundidade Heurística

**Requirement**: COGN-03
**Focus**: Heurísticas lexicais em tempo real para penalizar verbosidade oca.
**Success Criteria:**

- [ ] System includes `textstat` integration for computing real-time lexical complexity.
- [ ] Evaluator automatically flags and penalizes responses categorized as "verbosidade oca".
- [ ] MCTS tree prunes or lowers UCB score for heuristic-penalized nodes immediately.

### Phase 6: Mutador Cognitivo

**Requirement**: COGN-01
**Focus**: Injetar estruturas de raciocínio lógico (blocos pydantic) nas skills criadas.
**Success Criteria:**

- [ ] New strategy added to `StrategyRegistry` named `MutadorCognitivo`.
- [ ] Generated skills explicitly include required structured outputs (e.g., Pydantic schema constraints).
- [ ] MCTS successfully uses the cognitive mutator during its tree exploration.

### Phase 7: Otimização por Densificação Extrema

**Requirement**: COGN-04
**Focus**: Recompensar instruções comprimidas e altamente lógicas.
**Success Criteria:**

- [ ] Reward function mathematically boosts scores for answers that are both logical and concise.
- [ ] Verbose chain-of-thought results receive lower relative scores compared to dense logic.
- [ ] E2E pipeline successfully outputs compressed, highly-structured prompt variants.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Architectural Cleanup & Densification | v1.0 | 5/5 | Complete | 2026-07-09 |
| 2. Judge "Caça-Defeitos" Mode | v1.0 | 2/2 | Complete | 2026-07-09 |
| 3. Close gap: JUD-01, JUD-02 Fix optimizer.py to target Mode B | v1.0 | 1/1 | Complete | 2026-07-09 |
| 4. Avaliador de Profundidade Semântica | v1.1 | 1/2 | In Progress|  |
| 5. Avaliador de Profundidade Heurística | v1.1 | 0/0 | Pending | — |
| 6. Mutador Cognitivo | v1.1 | 0/0 | Pending | — |
| 7. Otimização por Densificação Extrema | v1.1 | 0/0 | Pending | — |
