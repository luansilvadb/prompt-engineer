from typing import Protocol, Any
from dataclasses import dataclass
from src.signatures import Avaliacao, AvaliacaoModoB, MutadorCognitivoOutput

class IAiFramework(Protocol):
    def context(self, lm: Any) -> Any:
        ...

@dataclass
class EstrategiaDescoberta:
    nome_estrategia: str
    prompt_estrategia: str

class IStrategyDiscoverer(Protocol):
    def __call__(self, skill_atual: str, feedbacks_recentes: str, estrategias_conhecidas: str) -> EstrategiaDescoberta:
        ...

@dataclass
class SelfReflectiveOutput:
    critica: str
    nova_instrucao: str

@dataclass
class MutadorCognitivoAgentOutput:
    critica: str
    raciocinio_estruturado: str
    nova_instrucao: str

class ISelfReflectiveAgent(Protocol):
    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str) -> SelfReflectiveOutput:
        ...

class IMutadorCognitivoAgent(Protocol):
    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str) -> MutadorCognitivoAgentOutput:
        ...

class IAvaliadorDeSkill(Protocol):
    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> Avaliacao:
        ...

class IAvaliadorModoB(Protocol):
    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        ...
