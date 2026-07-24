from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.signatures import AvaliacaoModoB


class IAiFramework(Protocol):
    def context(self, lm: Any) -> Any:
        ...


@dataclass(frozen=True)
class SelfReflectiveOutput:
    critica: str
    nova_instrucao: str


@dataclass(frozen=True)
class MutadorCognitivoAgentOutput:
    critica: str
    raciocinio_estruturado: str
    nova_instrucao: str


@dataclass
class DiscoveredStrategy:
    nome_estrategia: str
    prompt_estrategia: str

    def __post_init__(self):
        if self.nome_estrategia is None:
            object.__setattr__(self, 'nome_estrategia', '')


class IStrategyDiscoverer(Protocol):
    def __call__(
        self,
        skill_atual: str,
        feedbacks_recentes: str,
        estrategias_conhecidas: str,
    ) -> DiscoveredStrategy:
        ...


class ISelfReflectiveAgent(Protocol):
    def __call__(
        self,
        instrucao_anterior: str,
        nota_anterior: str,
        feedback_juiz: str,
        estrategia_mutacao: str,
    ) -> SelfReflectiveOutput:
        ...


class IMutadorCognitivoAgent(Protocol):
    def __call__(
        self,
        instrucao_anterior: str,
        nota_anterior: str,
        feedback_juiz: str,
        estrategia_mutacao: str,
    ) -> MutadorCognitivoAgentOutput:
        ...


class IAvaliadorModoB(Protocol):
    def __call__(
        self,
        skill_original: str,
        skill_otimizada: str,
        regras_adicionais: str,
    ) -> AvaliacaoModoB:
        ...
