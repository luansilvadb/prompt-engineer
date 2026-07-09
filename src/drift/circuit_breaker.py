import os
import time
from pathlib import Path
from typing import Optional

from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.drift.models import DriftReport, GateDecision, DriftThresholds

MODELS_DIR = Path('src/outputs/models')

def verificar_juiz_atual(thresholds: DriftThresholds, repetitions: int) -> Optional[DriftReport]:
    """
    Mede o juiz atualmente em produção contra o golden. Retorna None se golden vazio.
    """
    golden = GoldenSet()
    if golden.is_empty():
        return None

    runner = JudgeProbeRunner("atual")
    model_path = MODELS_DIR / 'avaliador_otimizado.json'
    if model_path.exists():
        runner.load_candidate(str(model_path))
    else:
        runner.as_zero()

    return medir_drift(runner, golden, repetitions, thresholds)

def circuit_breaker(thresholds: DriftThresholds, repetitions: int) -> GateDecision:
    """
    Se o juiz atual comprometeu o hard-gate, renomeia o arquivo para
    .drifted.bak — fazendo load_avaliador() cair no juiz zerado (BR4).
    """
    report = verificar_juiz_atual(thresholds, repetitions)
    if report is None:
        return GateDecision(True, "golden ausente; nada a verificar", None)

    if report.critical_rules_violated:
        model_path = MODELS_DIR / 'avaliador_otimizado.json'
        if model_path.exists():
            ts = time.strftime('%Y%m%d_%H%M%S')
            backup = MODELS_DIR / f'avaliador_otimizado.drifted.{ts}.bak'
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
