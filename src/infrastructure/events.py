from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from src.domain.events import CostEventPayload, EventLevel, IJobEventEmitter, NodeEventPayload


def _silence(*_args, **_kwargs) -> None:
    return None


class JobEventEmitter(IJobEventEmitter):
    """Adapta callbacks de transporte (SSE/CLI) ao protocolo IJobEventEmitter."""

    def __init__(
        self,
        on_log: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_node: Optional[Callable[[dict], None]] = None,
        on_cost: Optional[Callable[[dict], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
    ) -> None:
        self._on_log = on_log or _silence
        self._on_error = on_error or _silence
        self._on_node = on_node or _silence
        self._on_cost = on_cost or _silence
        self._is_cancelled = is_cancelled or (lambda: False)

    def emit_log(self, text: str, level: EventLevel = EventLevel.INFO) -> None:
        if level == EventLevel.ERROR:
            self._on_error(text)
        else:
            self._on_log(text)

    def emit_node(self, payload: NodeEventPayload) -> None:
        self._on_node(dataclasses.asdict(payload))

    def emit_cost(self, payload: CostEventPayload) -> None:
        self._on_cost(dataclasses.asdict(payload))

    def emit_error(self, message: str) -> None:
        self._on_error(message)

    def is_cancelled(self) -> bool:
        return self._is_cancelled()
