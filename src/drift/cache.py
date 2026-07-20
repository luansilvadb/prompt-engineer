import hashlib
import json
import os
from pathlib import Path
from typing import Optional

from src.drift.models import DriftReport, DimensionError
from src.drift.circuit_breaker import MODELS_DIR


def _drift_cache_path() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / 'drift_cache.json'


def _judge_config_hash() -> str:
    """
    Hash do conteúdo do modelo do juiz em produção + timestamp de modificação.
    Usado para invalidar o cache automaticamente quando o juiz é alterado.
    Retorna '' se o arquivo do modelo não existir (juiz zerado).
    """
    model_path = MODELS_DIR / 'avaliador_modo_b_otimizado.json'
    if not model_path.exists():
        return 'zero'
    try:
        content = model_path.read_bytes()
        mtime = str(model_path.stat().st_mtime)
        return hashlib.sha256(content + mtime.encode()).hexdigest()
    except Exception:
        return 'hash_error'


def load_drift_cache() -> Optional[DriftReport]:
    path = _drift_cache_path()
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Invalidação por hash: se o juiz mudou desde a última medição, cache é stale
        cached_hash = data.get('judge_config_hash', '')
        current_hash = _judge_config_hash()
        if cached_hash and current_hash and cached_hash != current_hash:
            return None
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
            style_gap=data.get('style_gap', 0.0),
            style_drift_signal=data.get('style_drift_signal', False),
            category_accuracy=data.get('category_accuracy', {}),
        )
    except Exception:
        return None


def save_drift_cache(report: DriftReport) -> None:
    """Persistência atômica do DriftReport do juiz em produção, incluindo hash da config."""
    path = _drift_cache_path()
    temp_path = path.with_suffix('.tmp')
    try:
        data = report.to_dict()
        data['judge_config_hash'] = _judge_config_hash()
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        print(f"[!] Falha ao salvar drift cache ({e}).")
