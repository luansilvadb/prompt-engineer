import json
import os
from pathlib import Path
from typing import Optional

from src.drift.models import DriftReport, DimensionError
from src.drift.circuit_breaker import MODELS_DIR

def _drift_cache_path() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / 'drift_cache.json'

def load_drift_cache() -> Optional[DriftReport]:
    path = _drift_cache_path()
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return DriftReport(
            judge_label=data.get('judge_label', 'atual'),
            spearman_composite=data.get('spearman_composite', 1.0),
            offset_scale=data.get('offset_scale', 0.0),
            mae_per_dimension=[DimensionError(**d) for d in data.get('mae_per_dimension', [])],
            critical_rules_concordance=data.get('critical_rules_concordance', 1.0),
            critical_rules_violated=data.get('critical_rules_violated', False),
            missed_violations=data.get('missed_violations', 0),
            false_rejections=data.get('false_rejections', 0),
            mean_variance=data.get('mean_variance', 0.0),
            repetitions=data.get('repetitions', 0),
            low_confidence=data.get('low_confidence', False),
        )
    except Exception:
        return None

def save_drift_cache(report: DriftReport) -> None:
    """Persistência atômica do DriftReport do juiz em produção."""
    path = _drift_cache_path()
    temp_path = path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        print(f"[!] Falha ao salvar drift cache ({e}).")
