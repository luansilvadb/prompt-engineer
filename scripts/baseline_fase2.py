"""
Baseline pre-Fase 2: mede o juiz atual (zero-shot Modo B) contra os 3 probes do golden set.
7 repeticoes por probe, reporta media e desvio-padrao.
"""
import sys
import json
import statistics
sys.path.insert(0, '.')

from src.config import setup, get_drift_thresholds
from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.drift.models import DriftThresholds
import dspy

def main():
    golden = GoldenSet()
    if golden.is_empty():
        print("[!] Golden set vazio. Abortando baseline.")
        return

    cfg = get_drift_thresholds()
    thresholds = DriftThresholds.from_config(cfg)
    repetitions = 7

    print(f"[*] Golden set: {len(golden.probes)} probes, {repetitions} repeticoes cada")
    for p in golden.probes:
        print(f"    {p.id}: rank_band={p.expected_rank_band}, composite={p.expected.composite_score():.3f}")

    # Juiz baseline: zero-shot (sem few-shot compilado)
    runner = JudgeProbeRunner("baseline_pre_fase2")
    runner.as_zero_modo_b()

    lm = setup()
    dspy.settings.configure(lm=lm)

    print("\n[*] Medindo drift do juiz baseline...")
    report = medir_drift(runner, golden, repetitions, thresholds)

    print("\n" + "=" * 60)
    print("RESUMO BASELINE (pre-Fase 2)")
    print("=" * 60)
    print(f"Spearman composite: {report.spearman_composite:.3f}")
    print(f"Offset scale:      {report.offset_scale:.2f}")
    print(f"Critical rules violated: {report.critical_rules_violated}")
    print(f"Missed violations:      {report.missed_violations}")
    print(f"False rejections:       {report.false_rejections}")
    print(f"Mean variance:          {report.mean_variance:.2f}")
    print(f"Low confidence:         {report.low_confidence}")

    print("\n--- Per Probe ---")
    for pp in report.per_probe:
        print(f"  {pp['probe_id']}: expected={pp['expected_composite']:.3f} "
              f"predicted={pp['predicted_composite']:.3f} "
              f"(variance={pp['variance']:.2f}) "
              f"critical_ok={pp['observed_critical_all_correct']} "
              f"missed={pp['missed_violations']} false_rej={pp['false_rejections']}")

    # Style gap (SD-1 vs SD-3)
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

    # Salvar relatorio para referencia futura
    report_dict = report.to_dict()
    report_dict['phase'] = 'baseline_pre_fase2'
    with open('src/outputs/golden/baseline_pre_fase2.json', 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
    print(f"\n[*] Relatorio salvo em src/outputs/golden/baseline_pre_fase2.json")

if __name__ == '__main__':
    main()