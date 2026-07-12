import math
import uuid
from typing import Optional, List

class MCTSNode:
    instruction: str
    q_value: float
    visits: int
    feedback: str
    children: List['MCTSNode']
    parent: Optional['MCTSNode']
    node_id: str
    critica: str
    mutation_strategy: str
    depth: int
    last_reward: float

    def __init__(
        self,
        instruction: str,
        parent: Optional['MCTSNode'] = None,
        feedback: str = '',
        node_id: Optional[str] = None,
        critica: str = '',
        mutation_strategy: str = '',
        depth: int = 0,
    ) -> None:
        self.instruction = instruction
        self.q_value = 0.0
        self.visits = 0
        self.feedback = feedback
        self.children = []
        self.parent = parent
        self.node_id = node_id if node_id else str(uuid.uuid4())
        self.critica = critica
        self.mutation_strategy = mutation_strategy
        self.depth = depth
        self.last_reward = 0.0

    def max_children_allowed(self, progressive_c: float, alpha: float) -> int:
        """
        Progressive Widening: max_children = ceil(C * visits^α).
        Nós mais visitados (promissores) ganham mais filhos.
        Nós com poucas visitas ficam com poucos filhos (poda natural).
        """
        if self.visits == 0:
            return 1
        return max(1, math.ceil(progressive_c * (self.visits ** alpha)))

    def best_child_ucb(self, c_param: float) -> Optional['MCTSNode']:
        """Seleção UCB1 padrão para a fase de seleção."""
        if not self.children:
            return None

        def ucb_score(child: 'MCTSNode') -> float:
            if child.visits == 0:
                return float('inf')
            return (child.q_value / child.visits) + c_param * math.sqrt(
                math.log(max(1, self.visits)) / child.visits
            )

        return max(self.children, key=ucb_score)
