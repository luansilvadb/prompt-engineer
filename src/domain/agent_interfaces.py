from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.signatures import Avaliacao, AvaliacaoModoB


class IAiFramework(Protocol):
    def context(self, lm: Any) -> Any:
        ...


@dataclass(frozen=True)
class StrategyDiscoveryInput:
    skill_atual: str
    feedbacks_recentes: str
    estrategias_conhecidas: str


@dataclass(frozen=True)
class DiscoveredStrategy:
    nome_estrategia: str
    prompt_estrategia: str


@dataclass(frozen=True)
class MutationInput:
    instrucao_anterior: str
    nota_anterior: str
    feedback_juiz: str
    estrategia_mutacao: str


@dataclass(frozen=True)
class SelfReflectiveOutput:
    critica: str
    nova_instrucao: str


@dataclass(frozen=True)
class MutadorCognitivoAgentOutput:
    critica: str
    raciocinio_estruturado: str
    nova_instrucao: str


# Kept for backward compatibility — callers use the non-frozen variants
@dataclass
class EstrategiaDescoberta:
    nome_estrategia: str
    prompt_estrategia: str


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


class IAvaliadorDeSkill(Protocol):
    def __call__(
        self,
        skill_original: str,
        skill_otimizada: str,
        regras_adicionais: str,
    ) -> Avaliacao:
        ...


class IAvaliadorModoB(Protocol):
    def __call__(
        self,
        skill_original: str,
        skill_otimizada: str,
        regras_adicionais: str,
    ) -> AvaliacaoModoB:
        ...
