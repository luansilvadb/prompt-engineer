"""
Drift Monitor — persistência de histórico de medições.
"""

import json
from pathlib import Path
from typing import List

from src.drift.circuit_breaker import MODELS_DIR


def _history_path() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / 'drift_history.json'


def load_drift_history() -> List[dict]:
    """Carrega todos os registros do histórico, mais recentes primeiro."""
    path = _history_path()
    if not path.exists():
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


