import threading
import math
import re
import uuid
from typing import Optional, List, Dict

class MCTSNode:
    instruction: str
    q_value: float
    sq_q_value: float
    visits: int
    feedback: str
    children: List['MCTSNode']
    parent: Optional['MCTSNode']
    node_id: str
    critica: str
    mutation_strategy: str
    depth: int
    last_reward: float
    prior: float
    virtual_losses: int
    lock: threading.Lock
    gate_ab_score: float
    gate_post_eval_score: float
    had_technical_error: bool

    def __init__(
        self,
        instruction: str,
        parent: Optional['MCTSNode'] = None,
        feedback: str = '',
        node_id: Optional[str] = None,
        critica: str = '',
        mutation_strategy: str = '',
        depth: int = 0,
        prior: float = 0.5,
    ) -> None:
        self.instruction = instruction
        self.q_value = 0.0
        self.sq_q_value = 0.0
        self.visits = 0
        self.feedback = feedback
        self.children = []
        self.parent = parent
        self.parents: List['MCTSNode'] = [parent] if parent is not None else []
        self.node_id = node_id if node_id else str(uuid.uuid4())
        self.critica = critica
        self.mutation_strategy = mutation_strategy
        self.depth = depth
        self.last_reward = 0.0
        self.prior = prior
        self.virtual_losses = 0
        self.is_sufficient: bool = False
        self.tried_strategies: set = set()
        self.reserved_strategies: set[str] = set()
        self.raw_reward: float = 0.0
        self.multiplied_reward: float = 0.0
        self.shaped_reward: float = 0.0
        self.gate_ab_score: float = 0.0
        self.gate_post_eval_score: float = 0.0
        self.had_technical_error: bool = False
        self.lock = threading.Lock()

    def add_parent(self, parent: 'MCTSNode') -> None:
        """Adiciona um nó pai alternativo para suporte a Grafos Orientados Acíclicos (DAG)."""
        if parent is None or parent is self:
            return
        with self.lock:
            if parent not in self.parents:
                self.parents.append(parent)
            if self.parent is None:
                self.parent = parent

    def variance(self) -> float:
        """Retorna a variância das recompensas observadas neste nó."""
        if self.visits <= 0:
            return 0.0
        mean = self.q_value / self.visits
        mean_sq = self.sq_q_value / self.visits
        return max(0.0, mean_sq - (mean ** 2))

    def add_virtual_loss(self) -> None:
        with self.lock:
            self.virtual_losses += 1

    def remove_virtual_loss(self) -> None:
        with self.lock:
            self.virtual_losses = max(0, self.virtual_losses - 1)

    def merge_stats(self, other: 'MCTSNode') -> None:
        """
        Swiechowski et al. Sec. 3.4 (Transposition Tables & DAGs):
        Funde estatísticas de visitas, q_value e sq_q_value de outro nó idêntico
        gerado por um caminho alternativo na árvore MCTS.
        """
        if other is self:
            return
        with self.lock, other.lock:
            if other.visits > 0:
                self.visits += other.visits
                self.q_value += other.q_value
                self.sq_q_value += other.sq_q_value
                if other.last_reward > self.last_reward:
                    self.last_reward = other.last_reward
                if other.gate_ab_score > self.gate_ab_score:
                    self.gate_ab_score = other.gate_ab_score
                if other.gate_post_eval_score > self.gate_post_eval_score:
                    self.gate_post_eval_score = other.gate_post_eval_score
                if other.had_technical_error:
                    self.had_technical_error = True

    def max_children_allowed(self, progressive_c: float, alpha: float) -> int:
        """
        Progressive Widening: max_children = ceil(C * visits^α).
        Nós mais visitados (promissores) ganham mais filhos.
        Nós com poucas visitas ficam com poucos filhos (poda natural).
        """
        effective_visits = max(0, self.visits + self.virtual_losses)
        if effective_visits == 0:
            return 1
        return max(1, math.ceil(progressive_c * (effective_visits ** alpha)))

    # DEPRECATED: Use src.domain.selection_policies.UCB1Policy instead.
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

    # DEPRECATED: Use src.domain.selection_policies.UCB1TunedPolicy instead.
    def best_child_ucb_tuned(
        self,
        c_param: float = 1.0,
        bandit_stats: Optional[Dict[str, float]] = None,
        rave_k: float = 10.0,
        virtual_loss_weight: float = 1.0,
    ) -> Optional['MCTSNode']:
        """Seleção UCB1-Tuned (Auer et al., 2002 / Survey Sec 3) ajustada pela variância com suporte a virtual loss e RAVE."""
        if not self.children:
            return None

        def ucb_tuned_score(child: 'MCTSNode') -> float:
            with child.lock:
                visits = child.visits + child.virtual_losses
                if visits == 0:
                    return float('inf')
                effective_q = child.q_value - (child.virtual_losses * virtual_loss_weight)
                mean = effective_q / visits

                if bandit_stats and child.mutation_strategy in bandit_stats:
                    q_rave = bandit_stats[child.mutation_strategy]
                    beta = math.sqrt(rave_k / (3 * max(1, self.visits) + rave_k))
                    mean = (1 - beta) * mean + beta * q_rave

                parent_visits = max(1, self.visits)
                v_i = child.variance() + math.sqrt((2.0 * math.log(parent_visits)) / visits)
                min_v = min(0.25, v_i)
                exploration = math.sqrt((math.log(parent_visits) / visits) * min_v)
                return mean + c_param * exploration

        return max(self.children, key=ucb_tuned_score)

    # DEPRECATED: Use src.domain.selection_policies.PUCTPolicy instead.
    def best_child_puct(
        self,
        c_param: float,
        bandit_stats: Optional[Dict[str, float]] = None,
        rave_k: float = 10.0,
        virtual_loss_weight: float = 1.0,
        c_bias: float = 0.5,
    ) -> Optional['MCTSNode']:
        """Seleção PUCT (AlphaZero-style) com RAVE (AMAF) e Progressive Bias (Chaslot et al.).
        Se bandit_stats for fornecido, funde a estimativa RAVE da estratégia com o Q-value local.
        O Progressive Bias (c_bias * prior / (1 + visits)) orienta a busca inicial para priors promissores."""
        if not self.children:
            return None

        def puct_score(child: 'MCTSNode') -> float:
            with child.lock:
                visits = child.visits + child.virtual_losses
                effective_q = child.q_value - (child.virtual_losses * virtual_loss_weight)
                q = effective_q / max(1, visits)
                
                if bandit_stats and child.mutation_strategy in bandit_stats:
                    q_rave = bandit_stats[child.mutation_strategy]
                    # Fórmula RAVE: decaimento de beta baseado em visits
                    beta = math.sqrt(rave_k / (3 * max(1, self.visits) + rave_k))
                    q = (1 - beta) * q + beta * q_rave

                # PUCT exploration term
                u = c_param * child.prior * math.sqrt(max(1, self.visits)) / (1 + visits)
                
                # Progressive Bias term (Chaslot et al.)
                progressive_bias = (c_bias * child.prior) / (1 + visits)
                
                return q + u + progressive_bias

        return max(self.children, key=puct_score)


class TranspositionTable:
    """
    Tabela de Transposição para MCTS (Swiechowski et al. Sec. 3.4 / MCTS Expert).
    Mapeia o hash do estado (instrução) para o nó canônico ou estatísticas compartilhadas,
    garantindo que nós idênticos gerados por diferentes caminhos de busca compartilhem
    q_value, visitas e histórico RAVE.
    """
    def __init__(self) -> None:
        self._table: Dict[str, MCTSNode] = {}
        self._lock = threading.Lock()
        self._transposition_hits: int = 0
        self._lookups: int = 0

    @staticmethod
    def _normalize_key(key: str) -> str:
        """
        Normaliza chaves de instrução para evitar duplicatas por variações superficiais
        de formatação, espaços, quebras de linha e cercas markdown.
        Swiechowski et al. Sec 3.4 (Transposition Tables & DAGs).
        """
        if not key:
            return ""
        normalized = key.replace("\r\n", "\n").strip()
        lines = [line.rstrip() for line in normalized.splitlines()]
        lines = _strip_markdown_fences(lines)
        clean_text = "\n".join(lines).strip()
        clean_text = _collapse_blank_lines(clean_text)
        return clean_text

    @property
    def hits(self) -> int:
        with self._lock:
            return self._transposition_hits

    @property
    def lookups(self) -> int:
        with self._lock:
            return self._lookups

    @property
    def hit_rate(self) -> float:
        with self._lock:
            if self._lookups == 0:
                return 0.0
            return self._transposition_hits / self._lookups

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._table)

    def get(self, key: str) -> Optional[MCTSNode]:
        norm_key = self._normalize_key(key)
        with self._lock:
            self._lookups += 1
            node = self._table.get(norm_key)
            if node is not None:
                self._transposition_hits += 1
            return node

    def put(self, key: str, node: MCTSNode) -> MCTSNode:
        norm_key = self._normalize_key(key)
        with self._lock:
            if norm_key in self._table:
                existing = self._table[norm_key]
                if existing is not node:
                    existing.merge_stats(node)
                    if node.parent:
                        existing.add_parent(node.parent)
                    for p in getattr(node, 'parents', []):
                        existing.add_parent(p)
                return existing
            self._table[norm_key] = node
            return node

    def contains(self, key: str) -> bool:
        norm_key = self._normalize_key(key)
        with self._lock:
            return norm_key in self._table

    def clear(self) -> None:
        with self._lock:
            self._table.clear()
            self._transposition_hits = 0
            self._lookups = 0


def _strip_markdown_fences(lines: list[str]) -> list[str]:
    """Remove linhas em branco das bordas e cercas markdown (ex: ``` ... ```)."""
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and lines[0].startswith("```"):
        lines.pop(0)
    if lines and lines and lines[-1].strip() == "```":
        lines.pop()
    return lines


def _collapse_blank_lines(text: str) -> str:
    """Normaliza múltiplas linhas em branco consecutivas em no máximo duas."""
    return re.sub(r'\n{3,}', '\n\n', text)



