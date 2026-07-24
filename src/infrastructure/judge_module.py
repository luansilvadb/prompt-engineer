import dspy
from src.utils.unicode_sanitizer import _sanitize_unicode_for_api


class JudgeModule(dspy.Module):
    """Módulo DSPY que encapsula o avaliador Modo B como um programa compilável."""

    def __init__(self):
        super().__init__()
        # Lazy import para evitar dependência circular:
        # dspy_impl.py → judge_module.py → dspy_impl.py
        from src.infrastructure.dspy_impl import AvaliadorModoBSignature
        self.judge = dspy.ChainOfThought(AvaliadorModoBSignature)

    def forward(self, skill_original: str, skill_otimizada: str, regras_adicionais: str):
        """Avalia uma skill otimizada contra a original."""
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'

        return self.judge(
            skill_original=_sanitize_unicode_for_api(skill_original),
            skill_otimizada=_sanitize_unicode_for_api(skill_otimizada),
            regras_adicionais=_sanitize_unicode_for_api(regras_adicionais),
        )
