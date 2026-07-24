"""
Métrica DSPY compilável — encapsula a função de recompensa composicional
como um dspy.Metric para uso com otimizadores nativos (GEPA, MIPROv2).
"""

from src.signatures import funcao_de_recompensa, calcular_composite, SCORE_WEIGHTS


def create_dspy_metric(judge_module):
    """
    Retorna uma função de métrica compatível com dspy.Metric.

    Assinatura: (example, pred, trace=None) -> float | bool

    Compatível com:
    - BootstrapFewShot: retorna True/False
    - GEPA: retorna float e popula pred.feedback
    - MIPROv2: retorna float
    """
    def metric(example, pred, trace=None):
        # Extrair campos do example e pred com segurança
        skill_original = getattr(example, 'skill_original', '')
        skill_otimizada = getattr(pred, 'skill_otimizada', '')
        regras_adicionais = getattr(example, 'regras_adicionais', '')

        if not skill_original or not skill_otimizada:
            return False

        # Usar a função de recompensa padrão
        score, feedback = funcao_de_recompensa(
            avaliador_modo_b=judge_module,
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais or '',
        )

        # Feedback rico para GEPA
        if trace is not None and hasattr(pred, 'feedback'):
            try:
                pred.feedback = feedback
            except Exception:
                pass

        return score

    return metric
