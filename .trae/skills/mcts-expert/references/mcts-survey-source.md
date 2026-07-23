# MCTS Survey — Supplementary Notes

Source: Świechowski, Godlewski, Sawicki, Mańdziuk (2021/2022), "Monte
Carlo Tree Search: A Review of Recent Modifications and Applications",
arXiv:2103.04931. This file holds material not already covered in
`vanilla-mcts.md`, `formulas.md`, or `decision-guide.md` — mostly extra
technique detail, domain-specific applications, and pointers for further
reading. It's a condensed, paraphrased companion, not a verbatim copy of
the paper; if the user wants the original text or exact citations, point
them to the arXiv paper (2103.04931).

## Classic pre-2012 enhancements (Sec. 2.3–2.5), still foundational

- **Transposition Tables** (Kishimoto & Schaeffer, 2002): originally an
  alpha-beta enhancement, adapted to MCTS to detect states reachable via
  different action sequences (transpositions) and merge their statistics.
  Turns the search "tree" into a DAG. Trade-off: harder to know which
  nodes are safe to deallocate after a real move is played, since nodes
  may be revisited. Often paired with RAVE.
- **History Heuristic** (Schaeffer, 1989): keep a global `Q(a)`/`N(a)` per
  action (independent of state) and bias rollouts toward historically
  good actions (ε-greedy or Boltzmann/roulette sampling).
- **Last-Good-Reply Policy (LGRP)** and **N-gram Selection Technique
  (NST)** (Tak et al., 2012): LGRP stores the best countermove to each
  action; NST generalizes this to statistics over action *sequences* of
  length N, used to bias both selection and simulation.
- **Opening/endgame books**: MCTS run offline with relaxed time limits can
  generate opening books; less commonly used for endgames since MCTS is
  already strong there.

## Master Combination examples (Sec. 4.5) — what "winning" agents look like

Competition-winning MCTS agents rarely rely on one trick; they stack
several enhancements addressing different phases:
- **Pac-Man/Ghost Team competition** (Pepels & Winands, 2012): variable-
  length tree edges (distance-aware), history-based playout biasing,
  policy switching to eliminate obviously-bad moves.
- **Mario** (Jacobsen et al., 2014): MixMax (amplify good-action rewards),
  macro-actions (multi-step avoidance sequences), partial expansion
  (skip obviously bad children), hole detection heuristic.
- **GVGP**: N-gram Selection + "Loss Avoidance" (immediately search for an
  alternative when a simulated loss occurs) raised average win-rate
  across 60+ games from ~31% to ~48% vs. vanilla MCTS (Soemers et al.,
  2016). Risk-seeking UCT modifications and reversal penalties also help
  (Frydenberg et al., 2015).
- **Hanabi** (cooperative game, Goodman 2019): Re-determinizing ISMCTS +
  action-space restriction rules, since cooperative play needs an
  established communication convention among agents.

Takeaway: best results come from combining 2–4 targeted enhancements, not
from picking one "best" technique — and there's no universal winner across
domains (the survey's recurring "no free lunch" theme, Sec. 2.5).

## Non-game applications, more detail

- **Chemical synthesis** (Segler et al., 2018, published in Nature):
  computer-aided retrosynthesis using three neural networks alongside
  MCTS — a rollout policy network (trained on ~17k reaction rules), an
  in-scope filter network (predicts whether a proposed transformation
  will actually work, pruning bad branches during expansion), and an
  expansion policy network (chooses which node to add, replacing
  first-untried-action expansion).
- **Security games** (Karwowski & Mańdziuk, several papers 2015–2020):
  MCTS-based approximation of Stackelberg Equilibria for patrolling
  schedules (defender vs. attacker). Key methods: **Mixed-UCT**
  (iteratively improves the leader's strategy against a gradually
  stronger follower built from past iterations) and **Double-Oracle UCT
  (O2UCT)** (alternates sampling the attacker's strategy space and
  constructing an optimal defender response). An extension incorporates
  **Anchoring Theory** to model human cognitive bias in the attacker.
- **Vehicle routing (CVRP and variants)**: common recipe is (1) generate a
  good initial solution via a classical heuristic (Clarke-Wright savings,
  a TSP solver), (2) use MCTS to explore incremental modifications
  (mutation-operator-style actions) or (3) factorize the problem — one
  tree per vehicle, synchronized during simulation. Macro-actions and
  depth-limited search with a fitness function for non-terminal states
  are common add-ons.
- **Robotics planning**: Dec-MCTS (Best et al., 2019) — decentralized,
  each robot keeps its own tree and periodically exchanges compressed
  summaries with others to update a joint policy distribution; useful for
  multi-robot online replanning.

## MCTS + Evolutionary Methods, more detail (Sec. 6)

- **Evolving heuristic functions**: genetic programming evolves a
  board-evaluation function used to bias playout action selection
  (Benbassat & Sipper, 2013). Effective but time-consuming — best done
  offline before the actual game/decision.
- **Evolving policies**: a weight vector shapes both tree and default
  policy, optimized via evolution strategies (Lucas et al., 2014; Perez
  et al., 2014's "KB Fast-Evo MCTS" dynamically extracts game features
  rather than using a fixed feature set).
- **Rolling Horizon Evolutionary Algorithm (RHEA)**: a *competitor* to
  MCTS, not an MCTS variant — evolves whole action sequences (genome =
  sequence of N actions) instead of doing tree search. Neither MCTS nor
  RHEA is universally stronger; depends on the game (Gaina et al., 2017a).
  Hybrids exist: RHEA-with-rollouts (blend RHEA fitness with MC rollout
  values) and ensemble (run RHEA then MCTS to check alternatives).
- **Evolutionary MCTS (EMCTS)** (Baier & Cowling, 2018): tree nodes hold
  whole action *sequences* (not single actions); edges are mutation
  operators; leaf sequences are evaluated with a heuristic instead of
  rollouts.

## Parallelization, more detail (Sec. 8)

Three base strategies (pick based on hardware/communication constraints —
see `decision-guide.md` "Performance / scaling"):

1. **Leaf Parallelization**: one shared tree; when a new node is
   expanded, run K independent playouts from it in parallel and average.
   Doesn't grow the tree faster, but makes new-node evaluation more
   accurate. Simplest to implement.
2. **Root Parallelization**: K independent trees built by K processes;
   aggregate first-level statistics only at decision time (weighted by
   visit count). Minimal communication overhead, doesn't produce deeper
   trees.
3. **Tree Parallelization**: one shared tree, multiple threads doing full
   iterations, synchronized with locks around expansion/backprop, and a
   **Virtual Loss** trick (temporarily assign a bad result to a node as
   soon as it's visited, corrected on backprop) to stop threads from
   collapsing onto the same path.

Root-Tree hybrids (Świechowski & Mańdziuk, 2016a) combine both for
distributed setups (worker/hub/master nodes) and scale further than either
alone. GPU-based leaf parallelism exists but requires porting the
simulator to run on-GPU — often impractical for complex domains.

## Where to look up things not in this file

If you need an exact citation, a specific numbered equation not listed in
`formulas.md`, or a niche application not summarized above, the
authoritative source is the paper itself: arXiv:2103.04931
("Monte Carlo Tree Search: A Review of Recent Modifications and
Applications"). Tables 1 and 2 in the paper's Conclusions section index
essentially every technique/paper by application domain and by method
category, respectively, if you want to point the user toward specific
further reading.
