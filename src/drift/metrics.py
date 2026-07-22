import statistics
from typing import List, Tuple

from src.drift.models import DriftReport, DimensionError
from src.drift.exceptions import DriftMeasurementError
# Lista configurável de buzzwords pomposas — consolidado em módulo único
from src.evaluators.buzzwords import STYLE_BUZZWORDS_LOWER as _STYLE_BUZZWORDS_LOWER


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
    """
    Mede todas as probes em paralelo usando ThreadPoolExecutor.
    Cada worker recebe seu próprio runner clonado (dspy.Predict não é thread-safe).
    O paralelismo reduz o tempo total de O(n_probes × repetitions) para
    O(repetitions) + overhead de thread, viabilizando o budget de timeout.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    from loguru import logger

    # max_workers semântico: até 4 threads concorrentes (balanceia throughput
    # contra rate-limit da API). Thread-safe porque cada worker opera seu
    # próprio runner clonado com dspy.Predict independente.
    max_workers = min(len(golden.probes), 4)
    lock = threading.Lock()
    results: list = [None] * len(golden.probes)
    errors: list = []

    def _measure_one(probe, idx: int):
        try:
            worker_runner = runner.clone()
            m = worker_runner.run(probe, repetitions)
            with lock:
                results[idx] = (probe, m)
        except Exception as e:
            with lock:
                errors.append((probe.id, str(e)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_measure_one, probe, idx): probe.id
            for idx, probe in enumerate(golden.probes)
        }
        for future in as_completed(futures):
            probe_id = futures[future]
            try:
                future.result()
            except Exception as e:
                errors.append((probe_id, str(e)))
                logger.warning("Probe {} falhou em thread worker: {}", probe_id, e)

    if errors:
        failed_ids = [pid for pid, _ in errors]
        error_msgs = '; '.join(f"{pid}: {msg[:120]}" for pid, msg in errors)
        raise DriftMeasurementError(
            f"Falha na medição paralela: {len(errors)}/{len(golden.probes)} probes falharam ({', '.join(failed_ids)})",
            context={'failed_probes': failed_ids, 'errors': error_msgs},
        )

    # Remove None entries (não deve acontecer se todos os futures completaram, mas é defesa)
    valid = [r for r in results if r is not None]
    if len(valid) != len(golden.probes):
        missing = len(golden.probes) - len(valid)
        raise DriftMeasurementError(
            f"{missing} probe(s) não retornaram resultado na medição paralela",
            context={'expected': len(golden.probes), 'got': len(valid)},
        )
    return valid


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


def _detect_style_drift_signal(measurements: list) -> bool:
    """
    Detecta sinal de viés estético analisando os feedbacks textuais do juiz.
    Se >40% dos feedbacks contêm >=2 buzzwords em contexto de elogio,
    retorna True como flag de auditoria.

    ATENÇÃO: Isto NUNCA penaliza automaticamente. É sinal para investigação humana.
    Threshold (>40%) é valor inicial — recalibrar na Fase 4 (DESIGN.md).
    """
    positive_signals = 0
    total_feedbacks = 0

    for _, m in measurements:
        for sample in m.samples:
            if sample is None:
                continue
            fb = getattr(sample, 'feedback_detalhado', '')
            if not fb:
                continue
            fb_lower = fb.lower()
            buzzword_count = sum(1 for bw in _STYLE_BUZZWORDS_LOWER if bw in fb_lower)
            # Verificar se o contexto é de elogio (palavras positivas próximas)
            praise_patterns = ['bom', 'boa', 'excelente', 'ótimo', 'otimo', 'bem estruturado',
                              'bem escrito', 'sofisticado', 'elegante', 'rico', 'impressionante']
            has_praise = any(p in fb_lower for p in praise_patterns)
            if buzzword_count >= 2 and has_praise:
                positive_signals += 1
            total_feedbacks += 1

    if total_feedbacks == 0:
        return False
    ratio = positive_signals / total_feedbacks
    return ratio > 0.40


def _compute_style_gap(measurements: list) -> float:
    """
    Computa style_gap = composite(SD1_integro) - composite(SD3_pomposo).
    Negativo = viés estético confirmado (alarme crítico).
    Retorna 0.0 se os probes não forem encontrados.
    """
    sd1_comp = None
    sd3_comp = None
    for p, m in measurements:
        if p.id == 'SD-1':
            sd1_comp = m.mean_composite()
        elif p.id == 'SD-3':
            sd3_comp = m.mean_composite()

    if sd1_comp is not None and sd3_comp is not None:
        return sd1_comp - sd3_comp
    return 0.0


def _compute_category_accuracy(measurements: list) -> dict:
    """
    Computa acurácia de critical_rules por categoria de probe.
    Retorna dict: {"estilo": 0.95, "general": 1.0, ...}
    """
    from collections import defaultdict
    cat_correct = defaultdict(int)
    cat_total = defaultdict(int)

    for p, m in measurements:
        cat = getattr(p, 'category', 'general')
        cat_total[cat] += 1
        if m.critical_rules_all_correct(p.expected.manteve_regras_criticas):
            cat_correct[cat] += 1

    return {
        cat: (cat_correct[cat] / cat_total[cat]) if cat_total[cat] > 0 else 0.0
        for cat in cat_total
    }


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

    # Fase 3: métricas de viés estético
    style_gap = _compute_style_gap(measurements)
    style_drift_signal = _detect_style_drift_signal(measurements)
    category_accuracy = _compute_category_accuracy(measurements)

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
        style_gap=style_gap,
        style_drift_signal=style_drift_signal,
        category_accuracy=category_accuracy,
    )
