import asyncio
import time
import dspy
from src.config import setup
from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.drift.models import DriftThresholds

# Desabilitar cache para garantir testes E2E reais e repetidos
dspy.settings.configure(cache=False)

lm = setup()
lm.cache = False

golden = GoldenSet()
runner = JudgeProbeRunner(label='DriftGate_E2E_NoCache')
runner.as_zero_modo_b()

thresholds = DriftThresholds()

print('[*] Rodando DriftGate Fim-a-Fim SEM CACHE com repetitions=3 (Demorará vários minutos...)')

start = time.time()
try:
    report = medir_drift(runner, golden, repetitions=3, thresholds=thresholds)
    
    print(f'\n[+] TEMPO: {time.time() - start:.1f}s')
    print(f'[+] RESULTADO FINAL DRIFT GATE')
    print(f'  - Spearman: {report.spearman_composite:.3f}')
    print(f'  - Viés Estético (Gap): {report.style_drift_signal}')
    print(f'  - Violations (Falsos + / Missed): {report.critical_rules_violated}')
    
    print('\n[*] Detalhes por Probe (Todos os 7):')
    for p in report.per_probe:
        print(f"  {p['probe_id']}:")
        print(f"    - Expected Composite: {p['expected_composite']:.3f} | Predicted Composite: {p['predicted_composite']:.3f}")
        print(f"    - Variance (3 runs): {p['variance']:.3f}")
        print(f"    - Expected Critical: {p['expected_critical']} | Observed All Correct: {p['observed_critical_all_correct']}")
        print(f"    - Missed Violations: {p['missed_violations']} | False Rejections: {p['false_rejections']}")
except Exception as e:
    import traceback
    traceback.print_exc()
