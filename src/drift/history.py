"""
Drift Monitor — persistência de histórico de medições.

Escrita atômica (tempfile + rename) com rotação FIFO:
mantém no máximo MAX_ENTRIES registros no arquivo drift_history.json.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

from src.drift.circuit_breaker import MODELS_DIR
from src.drift.models import DriftReport

MAX_ENTRIES = 100


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


def append_drift_report(report: DriftReport, triggered_cb: bool = False,
                        cb_reason: Optional[str] = None) -> None:
    """
    Adiciona um registro ao histórico com rotação FIFO (máx MAX_ENTRIES).
    Escrita atômica via tempfile + rename.
    """
    entries = load_drift_history()
    entry = report.to_dict()
    entry['circuit_breaker_triggered'] = triggered_cb
    if cb_reason:
        entry['circuit_breaker_reason'] = cb_reason

    # Inserir no início (mais recente primeiro)
    entries.insert(0, entry)

    # Rotação FIFO
    if len(entries) > MAX_ENTRIES:
        entries = entries[:MAX_ENTRIES]

    path = _history_path()
    temp_path = path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        print(f"[!] Falha ao salvar histórico de drift ({e}).")