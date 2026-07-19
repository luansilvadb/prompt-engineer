from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EventLevel(str, Enum):
    INFO = "info"
    ERROR = "error"


@dataclass(frozen=True)
class NodeEventPayload:
    id: str
    parent_id: str | None
    instruction: str
    feedback: str
    critica: str
    q_value: float
    visits: int
    score: float
    mutation_strategy: str
    depth: int
    job_id: str


class IJobEventEmitter:
    """
    Protocolo de emissão de eventos tipados para um job específico.
    Substitui os callbacks on_progress / on_error do Optimizer.
    """

    def emit_log(self, text: str, level: EventLevel = EventLevel.INFO) -> None:
        ...

    def emit_node(self, payload: NodeEventPayload) -> None:
        ...

    def emit_status(self, status: str) -> None:
        ...

    def emit_error(self, message: str) -> None:
        ...

    def is_cancelled(self) -> bool:
        ...