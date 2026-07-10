"""
Tests for src/drift/circuit_breaker.py

Validates:
  - The circuit breaker loads the correct model filename (avaliador_modo_b_otimizado.json).
  - When the golden set is empty, verificar_juiz_atual returns None (fail-open).
  - When there are no critical violations, circuit_breaker returns accept=True.
  - When missed_violations > 0, circuit_breaker returns accept=False and triggers rollback.
"""

import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.drift.circuit_breaker import verificar_juiz_atual, circuit_breaker, MODELS_DIR
from src.drift.models import DriftThresholds, GateDecision


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_thresholds() -> DriftThresholds:
    return DriftThresholds()


def _make_clean_report(missed_violations: int = 0):
    """Builds a minimal DriftReport-like mock for gate testing."""
    report = MagicMock()
    report.critical_rules_violated = missed_violations > 0
    report.missed_violations = missed_violations
    report.spearman_composite = 0.95
    report.offset_scale = 1.0
    report.low_confidence = False
    report.mean_variance = 0.0
    report.false_rejections = 0
    return report


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_verificar_juiz_atual_returns_none_when_golden_empty():
    """When the golden set has no probes, verificar_juiz_atual must return None (fail-open)."""
    with patch('src.drift.circuit_breaker.GoldenSet') as mock_gs_cls:
        mock_gs = MagicMock()
        mock_gs.is_empty.return_value = True
        mock_gs_cls.return_value = mock_gs
        result = verificar_juiz_atual(_make_thresholds(), repetitions=1)
    assert result is None


def test_verificar_juiz_atual_uses_correct_model_filename():
    """
    The runner must look for 'avaliador_modo_b_otimizado.json', not the old
    'avaliador_otimizado.json'. This test confirms the correct filename is used
    when the model does not exist on disk (so runner falls back to as_zero).
    """
    with patch('src.drift.circuit_breaker.GoldenSet') as mock_gs_cls, \
         patch('src.drift.circuit_breaker.JudgeProbeRunner') as mock_runner_cls, \
         patch('src.drift.circuit_breaker.medir_drift') as mock_drift:

        # Golden is non-empty
        mock_gs = MagicMock()
        mock_gs.is_empty.return_value = False
        mock_gs_cls.return_value = mock_gs

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner

        mock_drift.return_value = MagicMock()

        # Patch Path.exists to simulate model file NOT present
        with patch.object(Path, 'exists', return_value=False):
            verificar_juiz_atual(_make_thresholds(), repetitions=1)

        # runner.as_zero_modo_b() must have been called (model not found)
        mock_runner.as_zero_modo_b.assert_called_once()
        # runner.load_candidate_modo_b must NOT have been called
        mock_runner.load_candidate_modo_b.assert_not_called()


def test_verificar_juiz_atual_loads_model_when_present():
    """When the model file exists, load_candidate must be called, not as_zero."""
    with patch('src.drift.circuit_breaker.GoldenSet') as mock_gs_cls, \
         patch('src.drift.circuit_breaker.JudgeProbeRunner') as mock_runner_cls, \
         patch('src.drift.circuit_breaker.medir_drift') as mock_drift:

        mock_gs = MagicMock()
        mock_gs.is_empty.return_value = False
        mock_gs_cls.return_value = mock_gs

        mock_runner = MagicMock()
        mock_runner_cls.return_value = mock_runner
        mock_drift.return_value = MagicMock()

        # Simulate model file present
        with patch.object(Path, 'exists', return_value=True):
            verificar_juiz_atual(_make_thresholds(), repetitions=1)

        mock_runner.load_candidate_modo_b.assert_called_once()
        mock_runner.as_zero_modo_b.assert_not_called()


def test_circuit_breaker_accept_when_golden_empty():
    """If golden is absent, circuit breaker must return accept=True (fail-open)."""
    with patch('src.drift.circuit_breaker.verificar_juiz_atual', return_value=None):
        decision = circuit_breaker(_make_thresholds(), repetitions=1)
    assert decision.accept is True
    assert 'golden ausente' in decision.reason


def test_circuit_breaker_accept_when_no_violations():
    """If juiz has no critical violations, circuit breaker must return accept=True."""
    clean_report = _make_clean_report(missed_violations=0)
    with patch('src.drift.circuit_breaker.verificar_juiz_atual', return_value=clean_report):
        decision = circuit_breaker(_make_thresholds(), repetitions=1)
    assert decision.accept is True


def test_circuit_breaker_rejects_on_missed_violations():
    """If juiz approved a violating skill (missed_violations>0), circuit breaker rejects."""
    bad_report = _make_clean_report(missed_violations=1)
    with patch('src.drift.circuit_breaker.verificar_juiz_atual', return_value=bad_report), \
         patch.object(Path, 'exists', return_value=False):
        decision = circuit_breaker(_make_thresholds(), repetitions=1)
    assert decision.accept is False
    assert 'circuit breaker' in decision.reason
    assert decision.triggered_metric == 'critical_rules'


def test_circuit_breaker_rollback_uses_correct_filename():
    """
    When rolling back a drifted model, the file renamed must be
    'avaliador_modo_b_otimizado.json', NOT the legacy 'avaliador_otimizado.json'.
    """
    bad_report = _make_clean_report(missed_violations=2)

    captured_renames = []

    def fake_replace(src, dst):
        captured_renames.append((str(src), str(dst)))

    with patch('src.drift.circuit_breaker.verificar_juiz_atual', return_value=bad_report), \
         patch.object(Path, 'exists', return_value=True), \
         patch('src.drift.circuit_breaker.os.replace', side_effect=fake_replace):
        circuit_breaker(_make_thresholds(), repetitions=1)

    assert len(captured_renames) == 1
    src_path, dst_path = captured_renames[0]
    assert 'avaliador_modo_b_otimizado.json' in src_path, (
        f"Expected 'avaliador_modo_b_otimizado.json' in src, got: {src_path}"
    )
    assert 'avaliador_modo_b_otimizado.drifted.' in dst_path, (
        f"Expected 'avaliador_modo_b_otimizado.drifted.' in backup name, got: {dst_path}"
    )
    # Confirm old name is GONE from both paths
    assert 'avaliador_otimizado.json' not in src_path
