# Vanilla MCTS

Source: Świechowski et al., "Monte Carlo Tree Search: A Review of Recent
Modifications and Applications" (2021/2022), Section 2.

## Problem formalism (MDP)

MCTS applies to problems modeled as an MDP tuple `(S, A_s, P_a, R_a)`:

- `S` — set of possible states, with a distinguished initial state `s0`.
- `A_s` — actions available in state `s`.
- `P_a(s, s')` — transition probability of reaching `s'` from `s` via `a`
  (deterministic games: 1 if `a` leads from `s` to `s'`, else 0).
- `R_a(s)` — immediate reward for reaching `s` via `a`.

MCTS is directly applicable to MDPs. With modification (determinization,
information sets — see `decision-guide.md`) it extends to POMDPs
(partially observable, i.e. hidden-information problems).

## The four phases (one MCTS iteration)

1. **Selection** — starting at the root, repeatedly pick the child node
   according to the *tree policy* (usually UCT) until reaching a node that
   is either not fully expanded or a terminal state.
2. **Expansion** — unless a terminal state was reached, add (typically) one
   new child node to the tree, corresponding to an untried action from the
   selected node.
3. **Simulation** (rollout/playout) — from the new node, play out the
   problem (often randomly, "Monte Carlo" style) to a terminal state and
   obtain the reward/payoff. This is the phase most commonly enhanced with
   domain knowledge ("heavy playouts", see `decision-guide.md`).
4. **Backpropagation** — propagate the simulation's reward back up the path
   from the new node to the root, updating visit counts `N(s)`, `N(s,a)`
   and average reward `Q(s,a)` at every node along the way.

MCTS is run for as many iterations as the time/computation budget allows —
it is an **anytime algorithm**: it can be stopped at any point and still
return the currently-best action via:

```
a* = argmax_{a in A(s)} Q(s, a)
```

## Base tree policy: UCT

The dominant selection formula, Upper Confidence Bounds applied to Trees
(Kocsis & Szepesvári, 2006):

```
a* = argmax_{a in A(s)} [ Q(s,a) + C * sqrt( ln(N(s)) / N(s,a) ) ]
```

- `Q(s,a)` — average simulated result of action `a` in state `s` so far.
- `N(s)` — number of times state `s` has been visited.
- `N(s,a)` — number of times action `a` was sampled in state `s`.
- `C` — exploration constant, balances exploration vs. exploitation.
  Common first guess: `C = sqrt(2)`, assuming `Q` values are normalized to
  `[0, 1]`. **Always game/problem-dependent — tune empirically.**

Every action in a state is tried once before UCT scores are used to choose
among them.

## Minimal pseudocode shape

```
function MCTS(root_state, budget):
    root = Node(root_state)
    while budget remains:
        node = select(root)          # phase 1, walks tree via UCT
        if node is not terminal:
            node = expand(node)      # phase 2, adds one child
        reward = simulate(node)      # phase 3, random/heavy playout
        backpropagate(node, reward)  # phase 4, update Q/N up to root
    return best_action(root)         # e.g. argmax Q, or most-visited child
```

See `scripts/mcts_template.py` for a working Python implementation of this
shape, and `formulas.md` / `decision-guide.md` for how to swap in
enhancements at each phase.
