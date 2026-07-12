from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol


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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (0.0 <= self.total_score <= 1.0):
            raise ValueError("total_score must be in [0.0, 1.0]")


@dataclass
class MCTSNodeData:
    id: str
    parent_id: Optional[str]
    state_payload: Any
    visits: int = 0
    reward: float = 0.0
    status: NodeStatus = NodeStatus.PENDING
    evaluation: Optional[EvaluationScore] = None
    children_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MutationContext:
    target_node_id: str
    temperature: float
    constraints: Dict[str, Any]


@dataclass(frozen=True)
class OptimizationResult:
    best_node_id: str
    best_instruction: str
    best_score: float
    total_iterations: int
    execution_time_ms: float
    total_nodes_visited: int


class IMCTSNode(Protocol):
    """
    Contrato formal para o nó MCTS. Fecha GAP-04.
    MCTSNode em mcts.py deve satisfazer este Protocol estruturalmente.
    """

    @property
    def node_id(self) -> str:
        ...

    @property
    def instruction(self) -> str:
        ...

    @property
    def q_value(self) -> float:
        ...

    @property
    def visits(self) -> int:
        ...

    @property
    def feedback(self) -> str:
        ...

    @property
    def mutation_strategy(self) -> str:
        ...

    @property
    def depth(self) -> int:
        ...

    @property
    def last_reward(self) -> float:
        ...

    @property
    def parent(self) -> Optional["IMCTSNode"]:
        ...

    @property
    def children(self) -> List["IMCTSNode"]:
        ...

    def max_children_allowed(self, progressive_c: float, alpha: float) -> int:
        ...

    def best_child_ucb(self, c_param: float) -> Optional["IMCTSNode"]:
        ...


class IOptimizer(Protocol):
    """Contrato do motor de busca MCTS completo."""

    def optimize(self) -> str:
        ...

    def selection(self, node: IMCTSNode) -> IMCTSNode:
        ...

    def backpropagation(self, node: IMCTSNode, reward: float) -> None:
        ...


class IExperienceRepository(Protocol):
    """
    Contrato de domínio para acesso à memória Dyna-2.
    Separa responsabilidade de query do contrato de persistência.
    """

    def add(self, experience: Any) -> None:
        ...

    def save(self) -> None:
        ...

    def query_similar(self, feedback_query: str, top_k: int = 5) -> List[Any]:
        ...

    def get_strategy_stats(self) -> dict:
        ...

    @property
    def experiences(self) -> List[Any]:
        ...


class IEvaluator(Protocol):
    """
    Contrato base para qualquer avaliador de nós no MCTS.
    """

    def evaluate(self, node_data: MCTSNodeData) -> float:
        ...


class ISemanticEvaluator(IEvaluator, Protocol):
    def evaluate_semantics(self, payload: Any, expected_context: str) -> float:
        ...


class IHeuristicEvaluator(IEvaluator, Protocol):
    def evaluate_heuristics(self, payload: Any) -> float:
        ...


class IMutationStrategy(Protocol):
    """
    Contrato para estratégias de mutação que expandem a árvore MCTS.
    """

    def apply_mutation(self, node_data: MCTSNodeData, context: MutationContext) -> List[Any]:
        ...


class IExperienceStore(Protocol):
    """
    Contrato para salvar e carregar dados da árvore e histórico de execuções,
    isolando o domínio do banco de dados físico ou do disco.
    """

    def save_node(self, node: MCTSNodeData) -> None:
        ...

    def get_node(self, node_id: str) -> Optional[MCTSNodeData]:
        ...

    def update_node_status(self, node_id: str, new_status: NodeStatus) -> None:
        ...

    def save_optimization_result(self, result: OptimizationResult) -> None:
        ...


class IMCTSOptimizer(Protocol):
    """
    Contrato principal do orquestrador de busca.
    """

    def run_optimization(self, initial_state: Any, max_iterations: int) -> OptimizationResult:
        ...

    def step(self) -> None:
        ...


class OptimizerConfig(ABC):
    @abstractmethod
    def get_evaluators(self) -> List[IEvaluator]:
        pass

    @abstractmethod
    def get_mutator(self) -> IMutationStrategy:
        pass

    @abstractmethod
    def get_store(self) -> IExperienceStore:
        pass
