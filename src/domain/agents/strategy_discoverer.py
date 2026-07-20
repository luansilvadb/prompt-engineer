"""Strategy Discoverer — Agente DSPy que inventa novas estratégias de mutação."""
import dspy
from src.domain.agent_interfaces import IStrategyDiscoverer


class StrategyDiscovererSignature(dspy.Signature):
    skill_atual: str = dspy.InputField()
    feedbacks_recentes: str = dspy.InputField()
    estrategias_conhecidas: str = dspy.InputField()
    nome_estrategia: str = dspy.OutputField()
    prompt_estrategia: str = dspy.OutputField()


class StrategyDiscoverer(IStrategyDiscoverer):
    def __init__(self, lm=None):
        self.predictor = dspy.ChainOfThought(StrategyDiscovererSignature)

    def __call__(self, skill_atual: str, feedbacks_recentes: str, estrategias_conhecidas: str):
        return self.predictor(
            skill_atual=skill_atual,
            feedbacks_recentes=feedbacks_recentes,
            estrategias_conhecidas=estrategias_conhecidas,
        )