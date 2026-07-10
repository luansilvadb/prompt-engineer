from typing import Optional
from src.drift.models import DriftReport, GateDecision, DriftThresholds

def _gate_against_baseline_or_floor(cand_val: float, atual_val: Optional[float], threshold_abs: float, margin: float, better_when_lower: bool, metric_name: str, reason_fmt_baseline: str, reason_fmt_floor: str) -> Optional[GateDecision]:
    if atual_val is not None:
        if better_when_lower:
            if cand_val > atual_val + margin:
                return GateDecision(False, reason_fmt_baseline.format(cand_val, atual_val), metric_name)
        else:
            if cand_val < atual_val - margin:
                return GateDecision(False, reason_fmt_baseline.format(cand_val, atual_val), metric_name)
    else:
        if better_when_lower:
            if cand_val > threshold_abs:
                return GateDecision(False, reason_fmt_floor.format(cand_val, threshold_abs), metric_name)
        else:
            if cand_val < threshold_abs:
                return GateDecision(False, reason_fmt_floor.format(cand_val, threshold_abs), metric_name)
    return None

class DriftGate:
    """
    Portão defensivo hierárquico:
      Passo 1 — Veto absoluto (BR4): missed_violations > 0 → rejeita.
      Passo 2 — Spearman (Cenário 2 stealth): métrica rei de ranking.
      Passo 3 — Offset (Cenário 1 inflação): alarme de score inflado.
      Passo 4 — Confiança baixa: aceita com aviso (não rejeita).
    """

    @staticmethod
    def avaliar_candidato(report_cand: DriftReport,
                          report_atual: Optional[DriftReport],
                          thresholds: DriftThresholds) -> GateDecision:
        # Passo 1 — Veto absoluto: juiz aprovou skill que viola regra crítica (BR4 direcional).
        if report_cand.critical_rules_violated:
            return GateDecision(
                False,
                f"juiz aprovou {report_cand.missed_violations} violacao(oes) de regras criticas (missed_violations > 0)",
                "critical_rules",
            )

        # Passo 3 — Spearman (métrica rei: pega troca de ranking stealth).
        decision = _gate_against_baseline_or_floor(
            report_cand.spearman_composite,
            report_atual.spearman_composite if report_atual else None,
            thresholds.spearman_floor,
            thresholds.spearman_regression_margin,
            False,
            "spearman",
            "regressao de ranking (spearman {:.3f} vs atual {:.3f})",
            "spearman abaixo do floor ({:.3f} < {})"
        )
        if decision:
            return decision

        # Passo 4 — Offset (alarme de inflação — Cenário 1).
        decision = _gate_against_baseline_or_floor(
            report_cand.offset_scale,
            report_atual.offset_scale if report_atual else None,
            thresholds.offset_alarm,
            thresholds.offset_regression_margin,
            True,
            "offset",
            "inflacao de nota (offset {:.2f} vs atual {:.2f})",
            "inflacao de nota acima do alarme (offset {:.2f} > {})"
        )
        if decision:
            return decision

        # Passo 2 (aviso) — baixa confiança não rejeita, mas exige estrita melhoria
        if report_cand.low_confidence:
            return GateDecision(
                True,
                f"candidato aceito com BAIXA CONFIANCA (variancia {report_cand.mean_variance:.2f}); aumente DRIFT_REPETITIONS",
                None,
            )

        return GateDecision(True, "candidato nao regrediu", None)
