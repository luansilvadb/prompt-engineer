from dataclasses import dataclass, field
from typing import List, Optional, Any, Protocol
from enum import Enum

class NodeStatus(Enum):
    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    EXPANDED = "EXPANDED"
    TERMINAL = "TERMINAL"

@dataclass(frozen=True)
class EvaluationScore:
    heuristic_score: float
    semantic_score: float
    density_score: float
    total_score: float
    
    def __post_init__(self):
        if not (0.0 <= self.total_score <= 1.0):
            raise ValueError("O score total deve estar entre 0.0 e 1.0")

@dataclass
class NodeData:
    id: str
    state_payload: Any
    parent_id: Optional[str] = None
    visits: int = 0
    reward: float = 0.0
    status: NodeStatus = NodeStatus.PENDING
    evaluation: Optional[EvaluationScore] = None
    children_ids: List[str] = field(default_factory=list)
    depth: int = 0

    def add_visit(self, reward: float) -> None:
        self.visits += 1
        self.reward += reward

@dataclass(frozen=True)
class MutationContext:
    target_node_id: str
    temperature: float
    max_children: int

class IExperienceStore(Protocol):
    def save_node(self, node: NodeData) -> None:
        raise NotImplementedError

    def get_node(self, node_id: str) -> Optional[NodeData]:
        raise NotImplementedError
        
    def update_status(self, node_id: str, status: NodeStatus) -> None:
        raise NotImplementedError

class IEvaluator(Protocol):
    def evaluate(self, node: NodeData) -> EvaluationScore:
        raise NotImplementedError

class IMutationEngine(Protocol):
    def expand(self, node: NodeData, context: MutationContext) -> List[NodeData]:
        raise NotImplementedError

class ISelectionStrategy(Protocol):
    def select_best_child(self, node: NodeData, children: List[NodeData]) -> Optional[NodeData]:
        raise NotImplementedError

class IMCTSOptimizerUseCase(Protocol):
    def initialize_tree(self, initial_payload: Any) -> str:
        raise NotImplementedError
        
    def run_step(self) -> None:
        raise NotImplementedError
