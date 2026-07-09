import statistics
from typing import List, Tuple

from src.drift.models import DriftReport, DimensionError, GoldenProbe
from src.drift.exceptions import DriftMeasurementError


def _compute_ranks(values: List[float]) -> List[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    rank = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # postos 1-based
        for k in range(i, j + 1):
            rank[order[k]] = avg_rank
        i = j + 1
    return rank


def _spearman_rank_correlation(x: List[float], y: List[float]) -> float:
    """
    Correlação de postos de Spearman entre duas listas de mesmo comprimento.
    Implementação direta (sem scipy). Retorna 1.0 se n < 2 (sem ranking p/ corromper).
    Métrica REI do portão: pega Cenário 2 stealth (ranking trocado, notas estáveis).
    """
    n = len(x)
    if n < 2:
        return 1.0

    rx = _compute_ranks(x)
    ry = _compute_ranks(y)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def _measure_all_probes(runner, golden, repetitions: int) -> list:
    measurements = []
    for probe in golden.probes:
        m = runner.run(probe, repetitions)
        measurements.append((probe, m))
    return measurements


def _compute_mae_per_dimension(measurements: list, dims: List[str]) -> List[DimensionError]:
    mae_per_dim = []
    for d in dims:
        diffs = []
        for p, m in measurements:
            exp_val = getattr(p.expected, d)
            pred_val = m.mean_per_dimension().get(d, 0.0)
            diffs.append(abs(pred_val - exp_val))
        mae_per_dim.append(DimensionError(dimension=d, mae=statistics.mean(diffs) if diffs else 0.0))
    return mae_per_dim


def _compute_concordance_and_violations(measurements: list) -> Tuple[float, int, int]:
    if not measurements:
        return 0.0, 0, 0
    correct = sum(1 for p, m in measurements if m.critical_rules_all_correct(p.expected.manteve_regras_criticas))
    concordance = correct / len(measurements)
    total_missed = sum(m.missed_violation_count(p.expected.manteve_regras_criticas) for p, m in measurements)
    total_false_rej = sum(m.false_rejection_count(p.expected.manteve_regras_criticas) for p, m in measurements)
    return concordance, total_missed, total_false_rej


def _build_per_probe(measurements: list) -> List[dict]:
    per_probe = []
    for p, m in measurements:
        per_probe.append({
            'probe_id': p.id,
            'expected_composite': p.expected.composite_score(),
            'predicted_composite': m.mean_composite(),
            'variance': m.variance(),
            'expected_critical': p.expected.manteve_regras_criticas,
            'observed_critical_all_correct': m.critical_rules_all_correct(p.expected.manteve_regras_criticas),
            'missed_violations': m.missed_violation_count(p.expected.manteve_regras_criticas),
            'false_rejections': m.false_rejection_count(p.expected.manteve_regras_criticas),
        })
    return per_probe


def medir_drift(runner, golden, repetitions: int, thresholds) -> DriftReport:
    if golden.is_empty():
        raise DriftMeasurementError("Golden set vazio — nada a medir.")

    measurements = _measure_all_probes(runner, golden, repetitions)

    # Sequência por probe_id para parear esperado vs. previsto
    expected_composites = [p.expected.composite_score() for p, _ in measurements]
    predicted_composites = [m.mean_composite() for _, m in measurements]

    spearman = _spearman_rank_correlation(expected_composites, predicted_composites)
    offset_scale = (statistics.mean(predicted_composites) - statistics.mean(expected_composites)) * 100

    dims = ['nota_clareza', 'nota_formatacao', 'nota_robustez',
            'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade']
    mae_per_dim = _compute_mae_per_dimension(measurements, dims)

    concordance, total_missed, total_false_rej = _compute_concordance_and_violations(measurements)
    critical_violated = total_missed > 0

    variances = [m.variance() for _, m in measurements]
    mean_var = statistics.mean(variances) if variances else 0.0
    low_conf = mean_var > thresholds.variance_low_confidence

    per_probe = _build_per_probe(measurements)

    return DriftReport(
        judge_label=runner.label,
        spearman_composite=spearman,
        offset_scale=offset_scale,
        mae_per_dimension=mae_per_dim,
        critical_rules_concordance=concordance,
        critical_rules_violated=critical_violated,
        missed_violations=total_missed,
        false_rejections=total_false_rej,
        mean_variance=mean_var,
        repetitions=repetitions,
        per_probe=per_probe,
        low_confidence=low_conf,
    )
