"""
Generic, commented MCTS skeleton (vanilla UCT + optional RAVE / heavy
playouts / early termination hooks).

This is a STARTING POINT, not a drop-in library: adapt `State` to the
user's actual domain (implement legal_actions / apply / is_terminal /
reward / current_player for their problem), and wire in whichever
enhancement hooks are relevant per references/decision-guide.md.

Formulas implemented here map directly to references/formulas.md:
  - UCT selection            -> formulas.md #1
  - RAVE blending (optional) -> formulas.md #3
  - Early-termination hook   -> formulas.md #6 (plug in a heuristic eval)
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Domain interface — REPLACE with the user's actual game/problem logic.
# ---------------------------------------------------------------------------
class State:
    """Minimal interface MCTS needs from a domain state.

    Implement these for the user's actual problem:
    """

    def legal_actions(self) -> list[Any]:
        raise NotImplementedError

    def apply(self, action: Any) -> "State":
        """Return the resulting state; do not mutate self (or copy first)."""
        raise NotImplementedError

    def is_terminal(self) -> bool:
        raise NotImplementedError

    def reward(self, player: Any) -> float:
        """Terminal reward from `player`'s perspective, e.g. in [0, 1]."""
        raise NotImplementedError

    def current_player(self) -> Any:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Tree node
# ---------------------------------------------------------------------------
@dataclass
class Node:
    state: State
    parent: Optional["Node"] = None
    action_from_parent: Any = None
    children: dict = field(default_factory=dict)  # action -> Node
    untried_actions: Optional[list] = None
    visits: int = 0
    total_reward: float = 0.0
    # RAVE stats (optional; only used if rave=True in MCTS.__init__)
    rave_visits: dict = field(default_factory=dict)   # action -> int
    rave_reward: dict = field(default_factory=dict)   # action -> float

    def q(self) -> float:
        return self.total_reward / self.visits if self.visits else 0.0

    def is_fully_expanded(self) -> bool:
        if self.untried_actions is None:
            self.untried_actions = self.state.legal_actions()
        return len(self.untried_actions) == 0


# ---------------------------------------------------------------------------
# MCTS driver
# ---------------------------------------------------------------------------
class MCTS:
    def __init__(
        self,
        exploration_c: float = math.sqrt(2),
        rave: bool = False,
        rave_k: float = 300.0,
        rollout_policy: Optional[Callable[[State], Any]] = None,
        early_termination_depth: Optional[int] = None,
        evaluate_fn: Optional[Callable[[State, Any], float]] = None,
    ):
        """
        exploration_c: UCT constant C (formulas.md #1). Tune empirically;
            sqrt(2) is a reasonable starting point for rewards in [0,1].
        rave: enable RAVE blending (formulas.md #3). Good when many
            actions have roughly position-independent value.
        rave_k: RAVE equivalence constant. Tune empirically.
        rollout_policy: fn(state) -> action, used during simulation. If
            None, uniform random rollout. Replace with a heavy-playout
            heuristic (decision-guide.md "Domain knowledge availability")
            for stronger simulations.
        early_termination_depth: if set, rollouts are cut off after this
            many steps and `evaluate_fn` is used instead of playing to a
            terminal state (formulas.md #6). Requires evaluate_fn.
        evaluate_fn: fn(state, player) -> float in [0,1], used when a
            rollout is cut short by early_termination_depth.
        """
        self.c = exploration_c
        self.rave = rave
        self.rave_k = rave_k
        self.rollout_policy = rollout_policy or self._uniform_random_policy
        self.early_termination_depth = early_termination_depth
        self.evaluate_fn = evaluate_fn
        if early_termination_depth is not None and evaluate_fn is None:
            raise ValueError("evaluate_fn is required when early_termination_depth is set")

    def search(self, root_state: State, iterations: int) -> Any:
        """Run `iterations` MCTS iterations from root_state; return the
        action leading to the most-visited child (robust choice)."""
        root = Node(state=root_state)
        for _ in range(iterations):
            node = self._select(root)
            reward, played_actions = self._simulate(node)
            self._backpropagate(node, reward, played_actions)
        return max(root.children.items(), key=lambda kv: kv[1].visits)[0]

    # -- Phase 1: Selection ------------------------------------------------
    def _select(self, node: Node) -> Node:
        while not node.state.is_terminal():
            if not node.is_fully_expanded():
                return self._expand(node)
            node = self._uct_select_child(node)
        return node

    def _uct_select_child(self, node: Node) -> Node:
        log_n = math.log(node.visits) if node.visits > 0 else 0.0

        def uct_score(child: Node) -> float:
            if child.visits == 0:
                return float("inf")  # always try untried children first
            exploit = child.q()
            explore = self.c * math.sqrt(log_n / child.visits)
            if self.rave:
                exploit = self._rave_blend(node, child)
            return exploit + explore

        return max(node.children.values(), key=uct_score)

    def _rave_blend(self, parent: Node, child: Node) -> float:
        """formulas.md #3 — blend Q with pooled AMAF/RAVE statistics."""
        action = child.action_from_parent
        rave_n = parent.rave_visits.get(action, 0)
        rave_q = (parent.rave_reward.get(action, 0.0) / rave_n) if rave_n else 0.0
        beta = math.sqrt(self.rave_k / (3 * parent.visits + self.rave_k))
        return beta * rave_q + (1 - beta) * child.q()

    # -- Phase 2: Expansion --------------------------------------------------
    def _expand(self, node: Node) -> Node:
        if node.untried_actions is None:
            node.untried_actions = node.state.legal_actions()
        action = node.untried_actions.pop(random.randrange(len(node.untried_actions)))
        child_state = node.state.apply(action)
        child = Node(state=child_state, parent=node, action_from_parent=action)
        node.children[action] = child
        return child

    # -- Phase 3: Simulation --------------------------------------------------
    def _simulate(self, node: Node) -> tuple[float, list]:
        state = node.state
        player = state.current_player()
        played_actions = []
        depth = 0
        while not state.is_terminal():
            if self.early_termination_depth is not None and depth >= self.early_termination_depth:
                return self.evaluate_fn(state, player), played_actions
            action = self.rollout_policy(state)
            played_actions.append(action)
            state = state.apply(action)
            depth += 1
        return state.reward(player), played_actions

    def _uniform_random_policy(self, state: State) -> Any:
        return random.choice(state.legal_actions())

    # -- Phase 4: Backpropagation --------------------------------------------
    def _backpropagate(self, node: Node, reward: float, played_actions: list) -> None:
        while node is not None:
            node.visits += 1
            node.total_reward += reward
            if self.rave and node.parent is not None:
                # Update RAVE stats on the parent for every action played
                # anywhere in this simulation's path, not just the one taken
                # (AMAF idea, formulas.md #3).
                for action in played_actions:
                    node.parent.rave_visits[action] = node.parent.rave_visits.get(action, 0) + 1
                    node.parent.rave_reward[action] = node.parent.rave_reward.get(action, 0.0) + reward
            node = node.parent


# ---------------------------------------------------------------------------
# Example usage (replace State/MCTS wiring with the user's actual domain)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(__doc__)
    print("Implement the State interface for your domain, then:")
    print("    mcts = MCTS(exploration_c=1.41)")
    print("    best_action = mcts.search(initial_state, iterations=1000)")
