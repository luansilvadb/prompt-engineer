import os
import time
from pathlib import Path
from typing import Optional

from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.drift.models import DriftReport, GateDecision, DriftThresholds

MODELS_DIR = Path('src/outputs/models')


def _has_api_key() -> bool:
    """Pre-flight: verifica se há credencial de LLM configurada."""
    return bool(
        os.getenv("API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
    )


def verificar_juiz_atual(thresholds: DriftThresholds, repetitions: int) -> Optional[DriftReport]:
    """
    Mede o juiz atualmente em produção contra o golden. Retorna None se golden vazio.
    Responsabilidade única: MEDIÇÃO (zero efeito colateral).

    Pre-flight (P1-C5): se não há API key E não há modelo treinado, retorna None
    imediatamente — evita instanciar dspy.Predict e disparar chamadas LLM que
    fariam o runner travar em cascata de timeout. Defesa em profundidade: o
    endpoint /api/check-drift também verifica e mapeia para status 'no_api_key'.
    """
    golden = GoldenSet()
    if golden.is_empty():
        return None

    # Pre-flight: sem API key e sem modelo treinado → nada a medir (fail-fast).
    model_path = MODELS_DIR / 'avaliador_modo_b_otimizado.json'
    if not _has_api_key() and not model_path.exists():
        return None

    runner = JudgeProbeRunner("atual")
    if model_path.exists():
        runner.load_candidate_modo_b(str(model_path))
    else:
        runner.as_zero_modo_b()

    return medir_drift(runner, golden, repetitions, thresholds)


def _execute_circuit_breaker(report: DriftReport) -> GateDecision:
    """
    Executa a ação de circuit breaker a partir de um report JÁ MEDIDO.
    Se o juiz atual comprometeu o hard-gate, renomeia o arquivo para
    .drifted.bak — fazendo load_avaliador() cair no juiz zerado (BR4).

    Responsabilidade única: VETO + EFEITO COLATERAL (zero medição interna).
    Deve ser chamada APÓS verificar_juiz_atual() — nunca internamente.
    """
    if report.critical_rules_violated:
        model_path = MODELS_DIR / 'avaliador_modo_b_otimizado.json'
        if model_path.exists():
            ts = time.strftime('%Y%m%d_%H%M%S')
            backup = MODELS_DIR / f'avaliador_modo_b_otimizado.drifted.{ts}.bak'
            try:
                os.replace(model_path, backup)
                print(f"[!] CIRCUIT BREAKER: juiz atual aprovou {report.missed_violations} violação(ões) "
                      f"de regras críticas (missed_violations > 0). Rollback ao juiz zerado. Backup em {backup.name}.")
            except Exception as e:
                print(f"[!] Circuit breaker: falha ao isolar juiz driftado ({e}).")
        return GateDecision(
            False,
            f"circuit breaker: rollback ao juiz zerado ({report.missed_violations} violações aprovadas)",
            "critical_rules",
        )

    extra = ""
    if report.false_rejections > 0:
        extra = f"; {report.false_rejections} false_rejections (excesso de rigor, diagnostico)"
    return GateDecision(True, f"juiz atual ok (spearman {report.spearman_composite:.3f}, offset {report.offset_scale:.2f}{extra})", None)


def circuit_breaker(thresholds: DriftThresholds, repetitions: int) -> GateDecision:
    """
    Conveniência legada: mede + executa CB em uma chamada.
    Preferir verificar_juiz_atual() + _execute_circuit_breaker() separadamente
    para evitar medição dupla quando o report já existe.
    """
    report = verificar_juiz_atual(thresholds, repetitions)
    if report is None:
        return GateDecision(True, "golden ausente; nada a verificar", None)
    return _execute_circuit_breaker(report)
