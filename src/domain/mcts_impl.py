import uuid
import math
from typing import List, Optional, Any, Dict

from src.domain.mcts_design import (
    NodeStatus, EvaluationScore, NodeData, MutationContext,
    IExperienceStore, IEvaluator, IMutationEngine, ISelectionStrategy,
    IMCTSOptimizerUseCase
)

class InMemoryExperienceStore(IExperienceStore):
    def __init__(self) -> None:
        self._nodes: Dict[str, NodeData] = {}

    def save_node(self, node: NodeData) -> None:
        self._nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[NodeData]:
        return self._nodes.get(node_id)

    def update_status(self, node_id: str, status: NodeStatus) -> None:
        node = self.get_node(node_id)
        if node:
            node.status = status
            self.save_node(node)


class DummyEvaluator(IEvaluator):
    def evaluate(self, node: NodeData) -> EvaluationScore:
        return EvaluationScore(
            heuristic_score=0.5,
            semantic_score=0.5,
            density_score=0.5,
            total_score=0.5
        )


class DefaultMutationEngine(IMutationEngine):
    def expand(self, node: NodeData, context: MutationContext) -> List[NodeData]:
        children = []
        for _ in range(context.max_children):
            child = self._create_child_node(node)
            children.append(child)
            node.children_ids.append(child.id)
        return children

    def _create_child_node(self, parent: NodeData) -> NodeData:
        child_id = str(uuid.uuid4())
        return NodeData(
            id=child_id,
            state_payload=parent.state_payload,
            parent_id=parent.id,
            depth=parent.depth + 1
        )


class UCB1SelectionStrategy(ISelectionStrategy):
    def __init__(self, c_param: float = 1.41) -> None:
        self.c_param = c_param
        
    def select_best_child(self, node: NodeData, children: List[NodeData]) -> Optional[NodeData]:
        if not children:
            return None
            
        best_child = None
        best_score = float('-inf')
        
        for child in children:
            score = self._calculate_ucb_score(node.visits, child)
            if score > best_score:
                best_score = score
                best_child = child
                
        return best_child

    def _calculate_ucb_score(self, parent_visits: int, child: NodeData) -> float:
        if child.visits == 0:
            return float('inf')
        
        exploitation = child.reward / child.visits
        exploration = self.c_param * math.sqrt(math.log(max(1, parent_visits)) / child.visits)
        return exploitation + exploration


class MCTSOptimizerUseCase(IMCTSOptimizerUseCase):
    def __init__(
        self,
        store: IExperienceStore,
        evaluator: IEvaluator,
        mutation_engine: IMutationEngine,
        selection_strategy: ISelectionStrategy
    ) -> None:
        self._store = store
        self._evaluator = evaluator
        self._mutation_engine = mutation_engine
        self._selection_strategy = selection_strategy
        self._root_id: Optional[str] = None

    def initialize_tree(self, initial_payload: Any) -> str:
        root_id = str(uuid.uuid4())
        root_node = NodeData(
            id=root_id,
            state_payload=initial_payload,
            status=NodeStatus.PENDING
        )
        self._store.save_node(root_node)
        self._root_id = root_id
        return root_id

    def run_step(self) -> None:
        if not self._root_id:
            raise ValueError("Tree not initialized. Call initialize_tree first.")
            
        root = self._store.get_node(self._root_id)
        if not root:
            return
            
        leaf = self._select(root)
        
        if leaf.status != NodeStatus.TERMINAL:
            self._expand_and_evaluate(leaf)
            
        self._backpropagate(leaf)

    def _select(self, node: NodeData) -> NodeData:
        current = node
        while current.children_ids:
            children = self._get_children(current)
            if not children:
                break
                
            unvisited = self._get_unvisited_children(children)
            if unvisited:
                return unvisited[0]
                
            best_child = self._selection_strategy.select_best_child(current, children)
            if not best_child:
                break
            current = best_child
            
        return current
        
    def _get_children(self, node: NodeData) -> List[NodeData]:
        children = []
        for child_id in node.children_ids:
            child = self._store.get_node(child_id)
            if child:
                children.append(child)
        return children
        
    def _get_unvisited_children(self, children: List[NodeData]) -> List[NodeData]:
        return [child for child in children if child.visits == 0]

    def _expand_and_evaluate(self, node: NodeData) -> None:
        context = MutationContext(
            target_node_id=node.id,
            temperature=0.7,
            max_children=3
        )
        
        new_children = self._mutation_engine.expand(node, context)
        for child in new_children:
            child.evaluation = self._evaluator.evaluate(child)
            child.status = NodeStatus.EVALUATING
            self._store.save_node(child)
            
        node.status = NodeStatus.EXPANDED
        self._store.save_node(node)

    def _backpropagate(self, node: NodeData) -> None:
        current = node
        
        reward = 0.0
        if current.evaluation:
            reward = current.evaluation.total_score
            
        while current:
            current.add_visit(reward)
            self._store.save_node(current)
            
            if not current.parent_id:
                break
            current = self._store.get_node(current.parent_id)
