---
name: mcts-expert
description: "Expert assistant for designing and implementing Monte Carlo Tree Search (MCTS) algorithms and enhancements, grounded in the Swiechowski et al. survey on MCTS modifications and applications. Use when the user wants to implement, code, debug, extend, or optimize an MCTS-based agent or solver -- for games (perfect or imperfect information), planning, scheduling, vehicle routing, security games, or any sequential decision problem modeled as an MDP/POMDP. Covers vanilla MCTS phases, UCT and alternatives (UCB1-Tuned, PUCT, RAVE), action reduction, early termination, determinization, Information Set MCTS (ISMCTS) for hidden information, heavy playouts, MCTS + neural networks (AlphaZero style), MCTS + evolutionary methods, and parallelization (leaf/root/tree). Invoke explicitly when the user references this skill or asks for hands-on MCTS implementation help."
---

# MCTS Expert

A skill for helping the user **design and implement** Monte Carlo Tree Search
solutions, using the taxonomy and techniques catalogued in the survey paper
bundled with this skill (`references/mcts-survey-source.md` has the full
text if you need to look something up that isn't already summarized below).

This skill is implementation-first: the goal is working, well-structured code
that matches the user's problem characteristics — not just an explanation of
MCTS theory. Still, always ground technical choices (formulas, enhancement
names, parameter names) in the terminology from the survey so the user can
cross-reference the literature.

## Workflow

1. **Understand the problem.** Before writing code, figure out:
   - What is the domain? (board/card game, video game, planning/scheduling,
     routing, security game, other combinatorial problem)
   - Single-agent or multi-agent? Perfect or imperfect information?
   - Real-time constraints (e.g., <100ms/move) or looser time/iteration budget?
   - Branching factor: small (~tens), large (hundreds+), or huge (RTS-scale)?
   - Is there an existing simulator/forward model, or does one need to be built?
   - Target language/framework, and whether there's existing code to extend.

   If the user hasn't specified these, ask — but don't block on exhaustive
   detail. A reasonable default (perfect-information, turn-based, moderate
   branching factor) is fine to assume and state explicitly if the domain is
   ambiguous.

2. **Pick a baseline + enhancements.** Start from vanilla MCTS
   (`references/vanilla-mcts.md`) always. Then consult
   `references/decision-guide.md` to pick which enhancements apply, based on
   the problem characteristics from step 1. Don't over-engineer: only add
   enhancements that address a real weakness for this specific problem
   (huge branching factor → action reduction; hidden information → ISMCTS;
   tactical traps → MCTS-minimax hybrid; etc.). Vanilla MCTS is often the
   right starting point, with enhancements added iteratively.

3. **Implement.** Use `references/formulas.md` for exact equations
   (UCT, UCB1-Tuned, RAVE, PUCT, progressive bias, etc.) and
   `scripts/mcts_template.py` as a clean, generic, well-commented starting
   skeleton (Python) that already separates the four MCTS phases and has
   extension points for the enhancements described in `decision-guide.md`.
   Adapt naming/structure to the user's actual codebase and language;
   don't force the template's exact shape if the user's project has its
   own conventions.

4. **Tune parameters knowingly.** Flag which parameters need empirical
   tuning (exploration constant C, simulation/iteration budget, RAVE
   equivalence constant k, search depth limits, etc.) — see
   "Parameters to Tune" in `references/decision-guide.md`. Don't silently
   pick magic numbers; tell the user what they control and suggest
   starting values from the literature (e.g., C = √2 as a first guess for
   normalized rewards).

5. **Explain trade-offs, briefly.** After implementing, a short note on
   what the chosen enhancement(s) buy the user and what they cost (extra
   memory, extra bias, extra hyperparameters) is more useful than a long
   lecture. Point to the relevant survey section (e.g., "Sec. 4.2,
   Information Sets") so the user can dig deeper if they want.

## Reference files

- `references/vanilla-mcts.md` — the four-phase algorithm, base UCT formula,
  and the general MDP formalism. Read this first for any task.
- `references/formulas.md` — every named formula from the survey (UCT,
  UCB1-Tuned, RAVE, PUCT/AlphaZero selection rule, progressive bias, TD-UCT,
  etc.) with variable definitions, ready to translate into code.
- `references/decision-guide.md` — a catalog of enhancement categories
  (action reduction, early termination, determinization, ISMCTS, heavy
  playouts, policy update, opponent modelling, MCTS+ML, MCTS+evolutionary,
  parallelization) each with: what problem it solves, when to use it, and
  which section of the survey it comes from. Use this to select techniques
  in step 2 of the workflow.
- `references/mcts-survey-source.md` — full extracted text of the survey,
  for anything not already covered above (specific paper citations, niche
  domain applications like chemical synthesis or security games, etc.).
- `scripts/mcts_template.py` — generic, runnable, commented Python MCTS
  skeleton (vanilla + hooks for RAVE, heavy playouts, and early termination)
  to adapt as a starting point.
