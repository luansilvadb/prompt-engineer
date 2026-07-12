from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AuscultaInput:
    skill_original: str
    skill_otimizada: str
    regras_adicionais: str


@dataclass(frozen=True)
class AuscultaModoAOutput:
    avaliacao: Any  # Avaliacao


@dataclass(frozen=True)
class AuscultaModoBOutput:
    avaliacao: Any  # AvaliacaoModoB


class IAuscultaModoA(Protocol):
    """Contrato para o avaliador Modo A (few-shot compilado)."""

    def avaliar(self, input_: AuscultaInput) -> AuscultaModoAOutput:
        ...

    def load_compiled(self, path: str) -> None:
        ...


class IAuscultaModoB(Protocol):
    """Contrato para o avaliador Modo B (zero-shot / baseline)."""

    def avaliar(self, input_: AuscultaInput) -> AuscultaModoBOutput:
        ...

    def load_compiled(self, path: str) -> None:
        ...
