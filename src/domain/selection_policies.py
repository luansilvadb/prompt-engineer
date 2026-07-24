import math
from typing import Optional, Dict

from src.domain.mcts import MCTSNode
from src.domain.config import MCTSConfig


class ISelectionPolicy:
    """Interface abstrata para políticas de seleção MCTS."""

    def select(
        self,
        node: MCTSNode,
        config: MCTSConfig,
        bandit_stats: Optional[Dict[str, float]] = None,
    ) -> Optional[MCTSNode]:
        raise NotImplementedError


class PUCTPolicy(ISelectionPolicy):
    """Política PUCT (AlphaZero-style) com RAVE (AMAF) e Progressive Bias (Chaslot et al.)."""

    def select(
        self,
        node: MCTSNode,
        config: MCTSConfig,
        bandit_stats: Optional[Dict[str, float]] = None,
    ) -> Optional[MCTSNode]:
        if not node.children:
            return None

        rave_k = config.rave_k
        virtual_loss_weight = config.virtual_loss_weight
        c_param = config.c_param
        c_bias = config.c_bias

        def puct_score(child: MCTSNode) -> float:
            with child.lock:
                visits = child.visits + child.virtual_losses
                effective_q = child.q_value - (child.virtual_losses * virtual_loss_weight)
                q_raw = effective_q / max(1, visits)
                # Knowledge-Bias UCT: blend prior with observed Q-value
                kb_lambda = getattr(config, 'knowledge_bias_lambda', 0.3)
                q = kb_lambda * child.prior + (1 - kb_lambda) * q_raw

                if bandit_stats and child.mutation_strategy in bandit_stats:
                    q_rave = bandit_stats[child.mutation_strategy]
                    beta = math.sqrt(rave_k / (3 * max(1, node.visits) + rave_k))
                    q = (1 - beta) * q + beta * q_rave

                u = c_param * child.prior * math.sqrt(max(1, node.visits)) / (1 + visits)
                progressive_bias = (c_bias * child.prior) / (1 + visits)

                return q + u + progressive_bias

        return max(node.children, key=puct_score)


class UCB1Policy(ISelectionPolicy):
    """Política UCB1 padrão."""

    def select(
        self,
        node: MCTSNode,
        config: MCTSConfig,
        bandit_stats: Optional[Dict[str, float]] = None,
    ) -> Optional[MCTSNode]:
        if not node.children:
            return None

        c_param = config.c_param

        def ucb_score(child: MCTSNode) -> float:
            if child.visits == 0:
                return float("inf")
            q_raw = child.q_value / child.visits
            # Knowledge-Bias UCT: blend prior with observed Q-value
            kb_lambda = getattr(config, 'knowledge_bias_lambda', 0.3)
            q = kb_lambda * child.prior + (1 - kb_lambda) * q_raw
            return q + c_param * math.sqrt(
                math.log(max(1, node.visits)) / child.visits
            )

        return max(node.children, key=ucb_score)


class UCB1TunedPolicy(ISelectionPolicy):
    """Política UCB1-Tuned (Auer et al., 2002) ajustada pela variância com suporte a virtual loss e RAVE."""

    def select(
        self,
        node: MCTSNode,
        config: MCTSConfig,
        bandit_stats: Optional[Dict[str, float]] = None,
    ) -> Optional[MCTSNode]:
        if not node.children:
            return None

        c_param = config.c_param
        rave_k = config.rave_k
        virtual_loss_weight = config.virtual_loss_weight

        def ucb_tuned_score(child: MCTSNode) -> float:
            with child.lock:
                visits = child.visits + child.virtual_losses
                if visits == 0:
                    return float("inf")
                effective_q = child.q_value - (child.virtual_losses * virtual_loss_weight)
                mean = effective_q / visits

                if bandit_stats and child.mutation_strategy in bandit_stats:
                    q_rave = bandit_stats[child.mutation_strategy]
                    beta = math.sqrt(rave_k / (3 * max(1, node.visits) + rave_k))
                    mean = (1 - beta) * mean + beta * q_rave

                # Knowledge-Bias UCT: blend prior with observed Q-value
                kb_lambda = getattr(config, 'knowledge_bias_lambda', 0.3)
                mean = kb_lambda * child.prior + (1 - kb_lambda) * mean

                parent_visits = max(1, node.visits)
                v_i = child.variance() + math.sqrt((2.0 * math.log(parent_visits)) / visits)
                min_v = min(0.25, v_i)
                exploration = math.sqrt((math.log(parent_visits) / visits) * min_v)
                return mean + c_param * exploration

        return max(node.children, key=ucb_tuned_score)


def create_selection_policy(config: MCTSConfig) -> ISelectionPolicy:
    policy_map: Dict[str, type] = {
        "puct": PUCTPolicy,
        "ucb1_tuned": UCB1TunedPolicy,
        "ucb1": UCB1Policy,
    }
    cls = policy_map.get(config.selection_policy, PUCTPolicy)
    return cls()
