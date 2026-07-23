# MCTS Enhancement Decision Guide

Use this to pick which enhancement(s) to layer onto vanilla MCTS, based on
the problem's characteristics. Each entry: **symptom → fix**, with the
survey section for deeper reading in `mcts-survey-source.md`.

## Branching factor / search-space size

- **Huge branching factor** (RTS games, many simultaneous units) →
  **Action Reduction** (Sec. 3.1): heuristic move pruning, Beam Search +
  MCTS (BMCTS), options/macro-actions that bundle several primitive moves,
  constraints that prune illegal/bad branches. Also consider
  **Problem Factorization** (Sec. 7.5) — give each independent sub-agent
  (e.g. each vehicle/unit) its own tree, synchronized at decision time.
- **Actions have position-independent value** (e.g. Go-like games) →
  **RAVE / AMAF** (Sec. 2.2, 3.2) — see `formulas.md` #3.
- **Hierarchical structure exists in the action space** (subgoals,
  pick-up/put-down style tasks) → **Hierarchical MCTS** (Sec. 7.1.3),
  macro-actions defining subgoals with their own nested search.

## Time constraints

- **Real-time / short decision windows** (<100ms, arcade/RTS games) →
  **Early Termination** (Sec. 3.3): cut playouts short and evaluate with a
  heuristic/shallow-minimax instead of running to a terminal state — see
  `formulas.md` #6. Also consider **Model simplification** (granular
  games, proxy models) to cut per-simulation cost.
- **Budget allows many iterations** → vanilla MCTS + RAVE/heavy playouts
  are usually enough; don't over-engineer.

## Information structure

- **Perfect information** (all state visible, e.g. Chess/Go) → vanilla
  MCTS + UCT alternatives as needed (Sec. 3).
- **Imperfect/hidden information** (cards in hand, fog of war) → two main
  families (Sec. 4):
  - **Determinization / PIMC** (Sec. 4.1): sample a concrete hidden state,
    solve as perfect-information, repeat. Simple but suffers from
    *strategy fusion* and *non-locality* (Cowling et al. 2012a).
  - **Information Set MCTS (ISMCTS)** (Sec. 4.2): nodes represent
    information sets (states indistinguishable from the acting player's
    view) rather than single states. Generally reduces strategy-fusion
    problems vs. plain determinization — prefer this when feasible.
  - For **non-locality-heavy games** (e.g. poker-like), consider **Online
    Outcome Sampling** (Sec. 4.2), which targets Nash-equilibrium
    convergence better than ISMCTS.
- **Simulation phase needs to stay consistent with private info** (e.g.
  don't leak what's in your own hand) → **Recursive Imperfect Information
  MCTS (IIMCTS)** (Sec. 4.2).

## Domain knowledge availability

- **You have a heuristic evaluator, move-ordering rules, or expert data** →
  **Heavy Playouts** (Sec. 4.3): bias rollout action choice with
  heuristics (ε-greedy, roulette/Boltzmann sampling). Trade-off: more
  realistic simulations, but too much heuristic bias can hurt exploration
  and requires more implementation effort. Balance is problem-specific.
- **You want to bias the tree-building phase itself, not just rollouts** →
  **Policy Update** (Sec. 4.4): RIDE (`formulas.md` #10), weighted-move
  playout policies, or combined tree+playout heuristics. None is
  universally best — depends on the game.
- **You have (or can train) a policy/value network** →
  **MCTS + Neural Networks**, AlphaGo/AlphaZero style (Sec. 5.2–5.3) —
  see `formulas.md` #7. High payoff but needs substantial training data
  and infra; consider a lighter **knowledge-bias UCT** (`formulas.md` #8)
  if you only have a smaller predictive model, not a full policy/value net.
- **No good heuristic yet, but want to build one automatically** →
  **Evolving Heuristic Functions** (Sec. 6.1) or **Evolving Policies**
  (Sec. 6.2) via genetic programming — offline process, then plug the
  evolved function in as you would a hand-crafted heuristic.

## Tactical / evaluation pitfalls

- **Sharp tactical traps cause MCTS to be misled by early lucky
  simulations** (e.g. chess-like games) →
  **Sufficiency threshold** (Sec. 3.2, `formulas.md` #5) or
  **MCTS-minimax hybrids** (Sec. 3.2): shallow minimax at select tree
  levels to avoid averaging away critical forced lines.

## Opponent modelling

- **Multi-player game where predicting opponents matters** →
  Section 3.4 (perfect info) / 4.6 (imperfect info). Options include:
  action tables keyed on game features, focusing search on "your own"
  impact vs. opponents' ("OMA" abstractions), or full opponent policy
  networks trained on human/bot data (knowledge-bias UCT,
  `formulas.md` #8).
- **Need to imitate human play style** (not just win) →
  train a network to predict human move probabilities, blend into
  selection via knowledge bias (Sec. 4.6).

## Non-game combinatorial problems

- **Planning/POMDP** → standard MCTS applies directly; for large discrete
  action spaces use **state-action abstraction** (ASAP-UCT, Sec. 7.1.1) or
  **PROST**-style action pruning + reward-lock detection (Sec. 7.1.1).
- **Scheduling** → MCTS to generate initial solutions, refine with local
  search/hyper-heuristics (Sec. 7.4).
- **Vehicle routing** → combine problem factorization (one tree per
  vehicle) + macro-actions + a good initial solution from a classical
  heuristic (Clarke-Wright, TSP solver) (Sec. 7.5).
- **Security/patrolling games** → Mixed-UCT / Double-Oracle UCT for
  Stackelberg equilibrium approximation (Sec. 7.2) — specialized, consult
  `mcts-survey-source.md` directly if this is the domain.

## Performance / scaling

- **Need more iterations per second, single machine, multi-core** →
  **Tree Parallelization** with virtual loss (Sec. 8.1) is usually the
  best default: one shared tree, multiple threads, locks around
  expansion/backprop.
- **Communication overhead is the bottleneck / distributed setting** →
  **Root Parallelization** (independent trees, aggregate at root) has
  minimal communication cost; **Root-Tree hybrid** (Sec. 8.4) scales
  further.
- **GPU available and simulator can run on it** → Leaf-parallel rollouts
  on GPU threads (Sec. 8.2) — but requires porting the simulator to GPU,
  often infeasible for complex domains.

## Parameters to Tune

Regardless of which enhancements are chosen, flag these as needing
empirical tuning rather than hardcoding guesses:

- **Exploration constant `C`** in UCT (start: `sqrt(2)` for `[0,1]`
  rewards, but always game-dependent).
- **Simulation/iteration budget** (time-based or count-based).
- **RAVE equivalence constant `k`**, if using RAVE.
- **Search/simulation depth limits**, if using early termination or
  depth-limited search.
- **Heuristic bias weights** (`W` in progressive bias, `lambda` in
  network/rollout blends, `C_BT`/`K` in knowledge bias).
- **Beam width `W` and depth `d`**, if using Beam-Search MCTS.

The survey notes most papers tune these empirically (grid search / manual
experimentation) rather than deriving them analytically — there's no
universal default beyond `C ≈ sqrt(2)` as a starting point.
