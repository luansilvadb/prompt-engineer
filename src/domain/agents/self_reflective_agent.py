"""Self-Reflective Agent — Agente DSPy que aplica mutação com ChainOfThought."""
import dspy
from src.domain.agent_interfaces import ISelfReflectiveAgent


class SelfReflectiveSignature(dspy.Signature):
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField()
    estrategia_mutacao: str = dspy.InputField()
    critica: str = dspy.OutputField()
    nova_instrucao: str = dspy.OutputField()


class SelfReflectiveAgent(ISelfReflectiveAgent):
    def __init__(self, lm=None):
        self.predictor = dspy.ChainOfThought(SelfReflectiveSignature)

    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str):
        return self.predictor(
            instrucao_anterior=instrucao_anterior,
            nota_anterior=nota_anterior,
            feedback_juiz=feedback_juiz,
            estrategia_mutacao=estrategia_mutacao,
        )