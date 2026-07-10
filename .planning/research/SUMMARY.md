# Project Research Summary

**Project:** Prompt Optimization: Cognitive Densification (v1.1)
**Domain:** LLM Reasoning Optimization (MCTS, Prompt Engineering)
**Researched:** 2026-07-10
**Confidence:** HIGH

## Executive Summary

The v1.1 milestone focuses on "Cognitive Densification" for prompt optimization. Instead of basic few-shot or verbose CoT bootstrapping, this update aims to explicitly inject advanced reasoning protocols into generated prompts while rigorously penalizing shallow, superficial logic using a specialized judge within an existing Monte Carlo Tree Search (MCTS) pipeline.

The recommended approach builds strictly upon the v1.0 MCTS core architecture without modifying the core search logic itself. It accomplishes this via two major components: a Cognitive Mutator (`Mutador Cognitivo`) built on `pydantic` and `jinja2`, and a Depth Evaluator (`Avaliador de Profundidade`) that leverages `sentence-transformers` and `textstat` to evaluate semantic similarity and textual heuristics efficiently.

Key risks center around prompt bloat and latency. "Deep reasoning" instructions often inflate output size without adding value, and expensive LLM evaluations at every MCTS node can cripple optimization speed. Mitigations include strict token-efficiency penalties, heuristic filtering during tree traversal, and ensuring the judge isn't punishing concise correctness.

## Key Findings

### Recommended Stack

The stack focuses on structural validation, semantic distance calculations, and fast textual heuristics.
[See full details in STACK.md](STACK.md)

**Core technologies:**
- `pydantic` (^2.7.0): Extração e Validação Estrutural — For injecting strict reasoning protocols and forcing structured outputs.
- `sentence-transformers` (^3.0.0): Avaliação de Similaridade Semântica — For the Depth Evaluator to calculate cosine distance between answers and original prompts, penalizing shallow paraphrasing.
- `textstat` (^0.7.3): Heurísticas de Profundidade Textual — For real-time, LLM-free metrics on lexical complexity to quickly prune MCTS nodes with low entropy.

### Expected Features

The MVP features validate the core premise of cognitive densification without breaking current APIs.
[See full details in FEATURES.md](FEATURES.md)

**Must have (table stakes):**
- **Mutador Cognitivo (Reasoning Injection)** — Injects reasoning protocols into generated skills. Relies on the v1.0 mutation architecture.
- **Avaliador de Profundidade (Shallow Reasoning Penalty)** — Expands "Juiz Modo B" to verify reasoning depth and penalize superficial logic.

**Should have (competitive):**
- **Densificação Cognitiva** — The core differentiator that forces LLMs into a highly compressed, rigorous logical reasoning state instead of just verbose CoT.

**Defer (v2+):**
- **Custom Cognitive Protocols** — Allowing configuration of specific reasoning protocols (ToT, GoT).
- **Dynamic Strategy Selection** — MCTS dynamically picking mutation strategies based on node state.

### Architecture Approach

The architecture seamlessly integrates into the existing MCTS pipeline by modifying specific strategy endpoints and signatures, avoiding broad logic refactors.
[See full details in ARCHITECTURE.md](ARCHITECTURE.md)

**Major components:**
1. **StrategyRegistry (`src/mutation_strategies/registry.py`)** — Handles pre-seeded core strategies by injecting the new Cognitive Mutator into the multi-armed bandit distribution.
2. **AvaliadorModoB (`src/signatures.py`)** — The expanded Judge that evaluates "reasoning depth" and registers shallow reasoning as a logical defect for the MCTS reward function to penalize.
3. **Teleprompter (`src/teleprompter.py`)** — Recompiles the Judge to converge the new instructions against the Golden Set without regressions.

### Critical Pitfalls

Performance and latency are the highest risks when injecting complex reasoning and evaluations into an MCTS loop.
[See full details in PITFALLS.md](PITFALLS.md)

1. **Mutador Cognitivo Inflating Prompt Size (Prompt Bloat)** — Avoid by implementing token-efficiency penalties so the system favors compressed reasoning over verbose generation.
2. **Avaliador de Profundidade Penalizing Concise Correctness** — Avoid by calibrating the judge to value logical soundness and edge-case handling rather than just looking for explicit `<thought>` tags.
3. **MCTS Node Evaluation Bottleneck (Latency & Cost Explosion)** — Avoid by applying the heavy Depth Evaluator only on terminal or top-N nodes, using fast heuristics for standard tree traversal.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Avaliador de Profundidade (Depth Evaluator)
**Rationale:** The judge must be in place first to establish a reliable baseline and reward signal before we start introducing complex cognitive mutations. Without it, the mutator's output cannot be scored effectively.
**Delivers:** Expanded `AvaliadorModoB` and semantic distance metrics.
**Addresses:** Shallow Reasoning Penalty (Avaliador de Profundidade).
**Avoids:** Avaliador de Profundidade Penalizing Concise Correctness.

### Phase 2: Mutador Cognitivo (Cognitive Mutator)
**Rationale:** Once the evaluator can accurately judge depth and penalize shallowness, we can introduce the mutator to generate denser prompts.
**Delivers:** Pre-seeded cognitive mutation strategies in `StrategyRegistry`.
**Uses:** `pydantic`, `jinja2`.
**Implements:** StrategyRegistry modifications.

### Phase 3: Integration & Optimization (Teleprompter Recompilation)
**Rationale:** Integrating the mutator and judge back into the MCTS loop requires careful performance tuning and recompilation of the DSPy modules.
**Delivers:** Recompiled Judge against Golden Set and asynchronous batching for MCTS nodes.
**Uses:** `pytest-asyncio`, `sentence-transformers`, `textstat`.
**Implements:** `teleprompter.py` compilation, MCTS node evaluation bottleneck mitigation.

### Phase Ordering Rationale

- **Judge First:** Establishing the depth evaluation metric (Avaliador) is critical to give the MCTS the correct reward signal before generating new nodes.
- **Mutator Second:** With the judge working, the Mutador Cognitivo can start testing new reasoning paradigms without immediately steering the MCTS tree in the wrong direction.
- **Integration Last:** Performance optimizations (avoiding bottlenecks) are done once the components are working, ensuring we are optimizing a correct system.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3:** Integration & Optimization requires careful API rate limit research and asynchronous DSPy/LiteLLM pipeline evaluation to ensure HTTP 429s are avoided.

Phases with standard patterns (skip research-phase):
- **Phase 1 & 2:** Standard DSPy signature extensions and Pydantic schema validation.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Libraries are standard, well-documented, and fit the existing architecture. |
| Features | HIGH | MVPs are clearly constrained to current DSPy capabilities. |
| Architecture | HIGH | Integration points (`registry.py`, `signatures.py`) are clearly defined and isolated. |
| Pitfalls | HIGH | Known MCTS + LLM bottlenecks are explicitly recognized. |

**Overall confidence:** HIGH

### Gaps to Address

- **Latency Calibration:** It's unclear how exactly `textstat` and `sentence-transformers` performance will behave inside deeply nested MCTS rollouts; this will need empirical testing during Phase 3.
- **Token Constraints:** The exact threshold for penalizing prompt bloat (Mutador Cognitivo) needs calibration against real Golden Set tasks to ensure it doesn't stifle necessary reasoning.

## Sources

### Primary (HIGH confidence)
- DSPy Documentation — Typed Predictors and Assertions
- Pydantic Documentation — Structured LLM outputs
- Sentence-Transformers Docs — Cosine Similarity for Text Penalization

### Secondary (MEDIUM confidence)
- MCTS algorithm performance patterns
- LLM-as-a-judge best practices and calibration issues

### Tertiary (LOW confidence)
- N/A

---
*Research completed: 2026-07-10*
*Ready for roadmap: yes*
