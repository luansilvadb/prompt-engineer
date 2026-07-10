# Pitfalls Research

**Domain:** Prompt Optimization (MCTS, LLMs)
**Researched:** 2026-07-10
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Mutador Cognitivo Inflating Prompt Size (Prompt Bloat)

**What goes wrong:**
The Mutador Cognitivo injects reasoning protocols that simply make the prompt extremely long and verbose, rather than actually increasing the "cognitive density." MCTS may favor these longer prompts if the Judge incorrectly correlates length with reasoning depth.

**Why it happens:**
"Reasoning protocols" often translate to verbose Chain-of-Thought (CoT) templates. Developers focus on injecting these templates without adding constraints on the output token length during the mutation phase.

**How to avoid:**
Implement a strict token-efficiency penalty in the MCTS scoring logic. The Cognitive Mutator should be prompted to summarize, refactor, and densely pack the reasoning, rather than just appending new paragraphs.

**Warning signs:**
The generated skills/prompts double or triple in token count compared to the original baseline without a proportional increase in Golden Set performance.

**Phase to address:**
Criar o Mutador Cognitivo (v1.1 Active Phase)

---

### Pitfall 2: Avaliador de Profundidade Penalizing Concise Correctness

**What goes wrong:**
The Avaliador de Profundidade (Depth Evaluator) penalizes skills that provide highly efficient, correct, and straightforward answers simply because they do not explicitly output "deep reasoning" steps.

**Why it happens:**
The Judge's prompt is heavily instructed to look for "reasoning depth" or step-by-step logic. It interprets the absence of explicit verbosity or multi-step logic as "shallow", even when the task doesn't require it.

**How to avoid:**
Calibrate the Avaliador de Profundidade to evaluate depth based on *handling edge cases*, *logical soundness*, and *behavioral robustness* in the Golden Set outputs, rather than purely looking for reasoning artifacts (like `<thought>` blocks) in the text. 

**Warning signs:**
Golden Set examples that require straightforward or simple answers start failing, or the Judge assigns them low scores (e.g., < 0.5) while praising verbose but incorrect answers.

**Phase to address:**
Atualizar Juiz Modo B (v1.1 Active Phase)

---

### Pitfall 3: MCTS Node Evaluation Bottleneck (Latency & Cost Explosion)

**What goes wrong:**
The MCTS optimization becomes unacceptably slow or hits API rate limits because evaluating "depth" adds a very complex, slow, or expensive LLM call for every single rollout in the tree.

**Why it happens:**
Evaluating "reasoning depth" inherently requires a more capable (and slower) LLM model or a multi-step evaluation prompt. When multiplied by the branching factor and depth of the MCTS tree, the cost and latency skyrocket.

**How to avoid:**
Apply the Avaliador de Profundidade strategically. Instead of evaluating every single MCTS node, use a cheaper/faster heuristic during tree traversal, and only run the heavy Depth Evaluator on terminal nodes or the top N most promising branches.

**Warning signs:**
Optimization jobs take hours instead of minutes; API bills spike unexpectedly; frequent HTTP 429 Too Many Requests errors from LiteLLM/DSPy.

**Phase to address:**
Integration of Mutador & Avaliador into MCTS Pipeline (v1.1)

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using the most expensive/powerful LLM for the Depth Evaluator | Easy to get good depth evaluation without complex prompt engineering | Massive API costs and incredibly slow MCTS rollouts | Only during initial validation/MVP of the Avaliador |
| Hardcoding reasoning templates in the Mutador Cognitivo | Fast implementation of the mutation strategy | Mutator cannot adapt to different types of skills (e.g., math vs creative writing) | MVP of the Cognitive Mutator |
| Ignoring asynchronous execution for the new Judge | Simpler code logic | CPU idles while waiting for API, crippling MCTS speed | Never, especially with MCTS |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LiteLLM / DSPy | Not handling rate limits when the Avaliador de Profundidade drastically increases API calls per MCTS node | Implement robust retry with exponential backoff and strict concurrency limits in the evaluator |
| MCTS Persisted State (`outputs/`) | Failing to add the new "reasoning depth score" to the persisted JSON/JSONL schema, breaking backward compatibility | Extend the schema carefully, making new depth metrics optional for older runs so historical data remains valid |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Synchronous Depth Evaluation | MCTS is extremely slow; low CPU utilization | Asynchronous evaluation of MCTS nodes (batching API calls to the Judge) | When MCTS branching factor > 3 and depth > 3 |
| Deep tree searches with heavy mutators | Memory exhaustion or API budget depletion | Cap maximum MCTS depth and use aggressive pruning based on the Judge's early signals | At > 50 rollouts per optimization job |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Mutador Cognitivo dynamically fetching external reasoning templates | Prompt injection vulnerabilities in the generated skills | Strictly sanitize, hardcode, or internally control the reasoning protocols used by the Mutator |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent failures due to Avaliador de Profundidade rejecting all mutations | User runs the optimizer, waits 20 minutes, and gets the original prompt back with no explanation | Stream progress and surface sub-scores (e.g., "Depth Score: 0.2") via the FastAPI endpoint so users know *why* mutations fail |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Mutador Cognitivo:** Often missing token length constraints — verify generated prompts aren't just 3x longer without added value.
- [ ] **Avaliador de Profundidade:** Often missing calibration against simple, correct answers — verify it doesn't penalize elegant, concise solutions.
- [ ] **MCTS Integration:** Often missing concurrency limits — verify the increased API load doesn't cause HTTP 429s.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| MCTS optimization takes 10x longer due to Depth Evaluator | MEDIUM | Temporarily disable Depth Evaluator for intermediate nodes; apply it only as a final filter on the top N candidates |
| Prompt Bloat (Overly verbose skills) | LOW | Run a strict summarization mutator over the bloated skills to distill the reasoning back into a dense format |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Prompt Bloat (Mutador) | Criar o Mutador Cognitivo | Verify token count of output skill is <= 1.2x of input baseline |
| False Positives (Avaliador) | Atualizar Juiz Modo B | Verify pass rate on inherently simple Golden Set examples remains > 95% |
| API Rate Limits / Bottlenecks | Integration / Pipeline | Run full MCTS on a large Golden Set without encountering HTTP 429s |

## Sources

- MCTS algorithm performance patterns
- LLM-as-a-judge best practices and calibration issues
- Project `.planning/PROJECT.md` (v1.1 Densificação Cognitiva context)
- Personal experience with prompt optimization and DSPy integrations

---
*Pitfalls research for: Prompt Optimization (MCTS, LLMs)*
*Researched: 2026-07-10*
