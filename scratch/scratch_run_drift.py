import asyncio
import time
from src.config import setup
from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift
from src.drift.models import DriftThresholds

lm = setup()

golden = GoldenSet()
runner = JudgeProbeRunner(label='DriftGate_E2E')
runner.as_zero_modo_b()

thresholds = DriftThresholds()

print('[*] Rodando DriftGate Fim-a-Fim com repetitions=3 (Isso vai demorar uns 3-4 minutos...)')

start = time.time()
try:
    report = medir_drift(runner, golden, repetitions=3, thresholds=thresholds)
    
    print(f'\n[+] TEMPO: {time.time() - start:.1f}s')
    print(f'[+] RESULTADO FINAL DRIFT GATE:')
    print(f'  - Spearman: {report.spearman_composite:.3f}')
    print(f'  - Viés Estético (Gap): {report.style_drift_signal:.3f}')
    print(f'  - Violations (Falsos + / Missed): {report.critical_rules_violated}')
    
    print('\n[*] Detalhes por Probe:')
    for p in report.per_probe:
        if p['probe_id'].startswith('SD'):
            print(f"  {p['probe_id']} -> Esperado: {p['expected_composite']:.1f} | Previsto: {p['predicted_composite']:.1f}")
except Exception as e:
    import traceback
    traceback.print_exc()
