"""Mutador Cognitivo — Agente DSPy que aplica mutação estruturada."""
import dspy
from src.domain.agent_interfaces import IMutadorCognitivoAgent


class MutadorCognitivoSignature(dspy.Signature):
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField()
    estrategia_mutacao: str = dspy.InputField()
    raciocinio_estruturado: str = dspy.OutputField()
    critica: str = dspy.OutputField()
    nova_instrucao: str = dspy.OutputField()


class MutadorCognitivo(IMutadorCognitivoAgent):
    def __init__(self, lm=None):
        self.predictor = dspy.ChainOfThought(MutadorCognitivoSignature)

    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str):
        return self.predictor(
            instrucao_anterior=instrucao_anterior,
            nota_anterior=nota_anterior,
            feedback_juiz=feedback_juiz,
            estrategia_mutacao=estrategia_mutacao,
        )