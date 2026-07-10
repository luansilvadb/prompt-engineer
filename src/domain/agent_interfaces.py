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

class IProbeJudge(Protocol):
    def load(self, path: str) -> None:
        ...
    def as_zero(self) -> None:
        ...
    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> Avaliacao:
        ...

class IProbeJudgeModoB(Protocol):
    def load(self, path: str) -> None:
        ...
    def as_zero(self) -> None:
        ...
    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        ...

class JudgeRegistry:
    _judge_creator = None
    _judge_modo_b_creator = None
    _signature_modo_b = None

    @classmethod
    def register(cls, judge_creator, judge_modo_b_creator):
        cls._judge_creator = judge_creator
        cls._judge_modo_b_creator = judge_modo_b_creator

    @classmethod
    def register_signature_modo_b(cls, signature):
        cls._signature_modo_b = signature

    @classmethod
    def _ensure_registered(cls):
        if cls._judge_creator is None:
            try:
                from src.infrastructure.dspy_impl import DSPyProbeJudge, DSPyProbeJudgeModoB, AvaliadorModoBSignature
                cls.register(DSPyProbeJudge, DSPyProbeJudgeModoB)
                cls.register_signature_modo_b(AvaliadorModoBSignature)
            except ImportError:
                pass

    @classmethod
    def create_judge(cls) -> IProbeJudge:
        cls._ensure_registered()
        if cls._judge_creator is None:
            raise RuntimeError("JudgeRegistry: IProbeJudge creator not registered!")
        return cls._judge_creator()

    @classmethod
    def create_judge_modo_b(cls) -> IProbeJudgeModoB:
        cls._ensure_registered()
        if cls._judge_modo_b_creator is None:
            raise RuntimeError("JudgeRegistry: IProbeJudgeModoB creator not registered!")
        return cls._judge_modo_b_creator()

    @classmethod
    def get_signature_modo_b(cls):
        cls._ensure_registered()
        if cls._signature_modo_b is None:
            raise RuntimeError("JudgeRegistry: signature_modo_b not registered!")
        return cls._signature_modo_b
