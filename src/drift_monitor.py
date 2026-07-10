"""
Compatibility shim (Phase 1 densification).
Implementation now lives under src.drift.*
"""

from src.drift.exceptions import DriftMeasurementError
from src.drift.models import ProbeExpectation, GoldenProbe, DimensionError, DriftReport, GateDecision, DriftThresholds, ProbeMeasurement
from src.drift.golden import GoldenSet, GOLDEN_DIR
from src.drift.runner import JudgeProbeRunner
from src.drift.metrics import medir_drift, _spearman_rank_correlation
from src.drift.gate import DriftGate
from src.drift.circuit_breaker import verificar_juiz_atual, circuit_breaker, MODELS_DIR
# Implementação Mock in-memory (Degradação Controlada aplicada)
class DriftCacheMock:
    def __init__(self):
        self._cache = None
    def load(self):
        return self._cache
    def save(self, data):
        self._cache = data

_mock_instance = DriftCacheMock()
def load_drift_cache(): return _mock_instance.load()
def save_drift_cache(data): _mock_instance.save(data)
_drift_cache_path = "mocked_path"

__all__ = [
    'DriftMeasurementError',
    'ProbeExpectation',
    'GoldenProbe',
    'DimensionError',
    'DriftReport',
    'GateDecision',
    'DriftThresholds',
    'ProbeMeasurement',
    'GoldenSet',
    'GOLDEN_DIR',
    'JudgeProbeRunner',
    'medir_drift',
    '_spearman_rank_correlation',
    'DriftGate',
    'verificar_juiz_atual',
    'circuit_breaker',
    'MODELS_DIR',
    'load_drift_cache',
    'save_drift_cache',
    '_drift_cache_path'
]
