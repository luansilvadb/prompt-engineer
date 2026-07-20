"""
Medicao pos-Fase 2: avalia o juiz com Rules + Metrics + Swap
contra os 3 probes do golden set.

Compara com a baseline (pre-Fase 2) e reporta o delta.
"""
import sys
import json
import statistics
sys.path.insert(0, '.')

from src.config import setup, get_drift_thresholds
from src.drift.golden import GoldenSet
from src.drift.models import DriftThresholds, DriftReport, DimensionError, ProbeMeasurement
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.infrastructure.dspy_impl import DSPyAvaliadorModoB
from src.infrastructure.experimental.enhanced_judge import EnhancedJudge
import dspy


def measure_with_enhanced_judge(golden: GoldenSet, repetitions: int, thresholds: DriftThresholds) -> DriftReport:
    """
    Mede o drift usando o EnhancedJudge (Metrics + Swap).
    Nao usa JudgeProbeRunner porque precisamos injetar o EnhancedJudge.
    """
    # Criar o juiz base (com Rules na Signature) e wrappear com EnhancedJudge
    base_judge = DSPyAvaliadorModoB()
    enhanced = EnhancedJudge(base_judge)

    measurements = []
    for probe in golden.probes:
        pm = ProbeMeasurement(probe_id=probe.id)
        failures = 0
        for _ in range(repetitions):
            try:
                resultado = enhanced(
                    skill_original=probe.skill_original,
                    skill_otimizada=probe.skill_otimizada,
                    regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                )
                pm.samples.append(resultado)
            except Exception as e:
                failures += 1
                print(f"  [!] Falha no probe {probe.id}: {e}")

        if len(pm.samples) == 0:
            print(f"  [!] Todas as {repetitions} repeticoes falharam no probe {probe.id}.")
            # Criar sample vazio para nao quebrar
            from src.signatures import AvaliacaoModoB
            dummy = AvaliacaoModoB(
                manteve_regras_criticas=False,
                defeitos_encontrados=["erro de medicao"],
                nota_clareza=0, nota_formatacao=0, nota_robustez=0,
                nota_densidade_informacional=0, nota_acionabilidade=0,
                nota_anti_fragilidade=0, feedback_detalhado="falha na medicao"
            )
            pm.samples.append(dummy)

        measurements.append((probe, pm))

    # Replicar logica de medir_drift
    from src.drift.metrics import _spearman_rank_correlation

    expected_composites = [p.expected.composite_score() for p, _ in measurements]
    predicted_composites = [m.mean_composite() for _, m in measurements]

    spearman = _spearman_rank_correlation(expected_composites, predicted_composites)
    offset_scale = (statistics.mean(predicted_composites) - statistics.mean(expected_composites)) * 100

    dims = ['nota_clareza', 'nota_formatacao', 'nota_robustez',
            'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade']

    mae_per_dim = []
    for d in dims:
        diffs = []
        for p, m in measurements:
            exp_val = getattr(p.expected, d)
            pred_val = m.mean_per_dimension().get(d, 0.0)
            diffs.append(abs(pred_val - exp_val))
        mae_per_dim.append(DimensionError(dimension=d, mae=statistics.mean(diffs) if diffs else 0.0))

    correct = sum(1 for p, m in measurements if m.critical_rules_all_correct(p.expected.manteve_regras_criticas))
    concordance = correct / len(measurements) if measurements else 0.0
    total_missed = sum(m.missed_violation_count(p.expected.manteve_regras_criticas) for p, m in measurements)
    total_false_rej = sum(m.false_rejection_count(p.expected.manteve_regras_criticas) for p, m in measurements)
    critical_violated = total_missed > 0

    variances = [m.variance() for _, m in measurements]
    mean_var = statistics.mean(variances) if variances else 0.0
    low_conf = mean_var > thresholds.variance_low_confidence

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

    return DriftReport(
        judge_label='enhanced_pos_fase2',
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


def load_baseline():
    """Carrega o relatorio da baseline pre-Fase 2."""
    path = 'src/outputs/golden/baseline_pre_fase2.json'
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def main():
    golden = GoldenSet()
    if golden.is_empty():
        print("[!] Golden set vazio. Abortando.")
        return

    cfg = get_drift_thresholds()
    thresholds = DriftThresholds.from_config(cfg)
    repetitions = 7

    print(f"[*] Golden set: {len(golden.probes)} probes, {repetitions} repeticoes cada")
    for p in golden.probes:
        print(f"    {p.id}: rank_band={p.expected_rank_band}, composite={p.expected.composite_score():.3f}")

    lm = setup()
    dspy.settings.configure(lm=lm)

    print("\n[*] Medindo drift do juiz ENHANCED (Rules + Metrics + Swap)...")
    report = measure_with_enhanced_judge(golden, repetitions, thresholds)

    # Carregar baseline
    baseline = load_baseline()

    print("\n" + "=" * 70)
    print("COMPARACAO: Baseline vs Pos-Fase 2 (Rules + Metrics + Swap)")
    print("=" * 70)

    print(f"\n{'Metrica':<35} {'Baseline':>12} {'Pos-Fase2':>12} {'Delta':>12}")
    print("-" * 71)

    baseline_spearman = baseline.get('spearman_composite', 0) if baseline else 0
    baseline_offset = baseline.get('offset_scale', 0) if baseline else 0
    baseline_missed = baseline.get('missed_violations', 0) if baseline else 0
    baseline_false_rej = baseline.get('false_rejections', 0) if baseline else 0
    baseline_meanvar = baseline.get('mean_variance', 0) if baseline else 0

    print(f"{'Spearman composite':<35} {baseline_spearman:>12.3f} {report.spearman_composite:>12.3f} {report.spearman_composite - baseline_spearman:>+12.3f}")
    print(f"{'Offset scale':<35} {baseline_offset:>12.2f} {report.offset_scale:>12.2f} {report.offset_scale - baseline_offset:>+12.2f}")
    print(f"{'Missed violations':<35} {baseline_missed:>12} {report.missed_violations:>12} {report.missed_violations - baseline_missed:>+12}")
    print(f"{'False rejections':<35} {baseline_false_rej:>12} {report.false_rejections:>12} {report.false_rejections - baseline_false_rej:>+12}")
    print(f"{'Mean variance':<35} {baseline_meanvar:>12.2f} {report.mean_variance:>12.2f} {report.mean_variance - baseline_meanvar:>+12.2f}")

    print(f"\n--- Per Probe ---")
    for pp in report.per_probe:
        print(f"  {pp['probe_id']}: expected={pp['expected_composite']:.3f} "
              f"predicted={pp['predicted_composite']:.3f} "
              f"(variance={pp['variance']:.2f}) "
              f"critical_ok={pp['observed_critical_all_correct']} "
              f"missed={pp['missed_violations']} false_rej={pp['false_rejections']}")

    # Style gap
    sd1_comp = None
    sd3_comp = None
    for pp in report.per_probe:
        if pp['probe_id'] == 'SD-1':
            sd1_comp = pp['predicted_composite']
        elif pp['probe_id'] == 'SD-3':
            sd3_comp = pp['predicted_composite']

    if sd1_comp is not None and sd3_comp is not None:
        style_gap = sd1_comp - sd3_comp
        print(f"\n--- Style Gap (SD-1 - SD-3) ---")
        print(f"  SD-1 (integro):  {sd1_comp:.3f}")
        print(f"  SD-3 (pomposo):  {sd3_comp:.3f}")
        print(f"  Style gap:       {style_gap:.3f} {'(OK - integro > pomposo)' if style_gap > 0 else '(VIES ESTETICO CONFIRMADO!)' if style_gap < 0 else '(zona de atencao)'}")

    # Salvar relatorio
    report_dict = report.to_dict()
    report_dict['phase'] = 'pos_fase2'
    with open('src/outputs/golden/pos_fase2.json', 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
    print(f"\n[*] Relatorio salvo em src/outputs/golden/pos_fase2.json")

    print("\n" + "=" * 70)
    print("CHECKPOINT FASE 2 — Aguardando aprovacao antes da Fase 3.")
    print("=" * 70)


if __name__ == '__main__':
    main()