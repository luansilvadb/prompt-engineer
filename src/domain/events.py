from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union


class EventLevel(str, Enum):
    INFO = "info"
    ERROR = "error"


class EventType(str, Enum):
    LOG = "log"
    NODE = "node"
    STATUS = "status"
    ERROR = "error"


@dataclass(frozen=True)
class LogEventPayload:
    text: str
    level: EventLevel
    job_id: str


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


@dataclass(frozen=True)
class StatusEventPayload:
    status: str
    job_id: str


@dataclass(frozen=True)
class ErrorEventPayload:
    message: str
    job_id: str


@dataclass(frozen=True)
class TypedSSEEvent:
    type: EventType
    data: Union[LogEventPayload, NodeEventPayload, StatusEventPayload, ErrorEventPayload]

    def to_sse_dict(self) -> dict:
        import dataclasses
        return {
            "type": self.type.value,
            "data": dataclasses.asdict(self.data),
        }


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
