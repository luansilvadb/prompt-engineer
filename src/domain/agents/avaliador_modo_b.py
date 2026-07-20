"""Avaliador Modo B — Implementação DSPy do juiz."""
import dspy
from src.domain.agent_interfaces import IAvaliadorModoB


class AvaliadorModoB(IAvaliadorModoB):
    def __init__(self, lm=None):
        self.lm = lm
        self.module = self._build_module()

    def _build_module(self) -> dspy.Module:
        from src.infrastructure.dspy_impl import AvaliadorModoBSignature
        return dspy.Predict(AvaliadorModoBSignature)

    def __call__(self, instrucao_original: str, instrucao_otimizada: str, regras_adicionais: str = ""):
        return self.module(
            instrucao_original=instrucao_original,
            instrucao_otimizada=instrucao_otimizada,
            regras_adicionais=regras_adicionais,
        )