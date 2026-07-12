from src.drift.gate import DriftGate
from src.drift.models import DriftReport, DriftThresholds

def test_drift_gate_accept():
    # Happy path: no regressions, high confidence, no critical rule violations.
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.9,
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = DriftReport(
        judge_label="Atual",
        spearman_composite=0.85,
        offset_scale=6.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is True
    assert "candidato nao regrediu" in decision.reason
    assert decision.triggered_metric is None

def test_drift_gate_veto_critical_rules():
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.9,
        offset_scale=5.0,
        critical_rules_violated=True,
        missed_violations=2,
        low_confidence=False
    )
    atual = None
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is False
    assert "juiz aprovou 2 violacao(oes)" in decision.reason
    assert decision.triggered_metric == "critical_rules"

def test_drift_gate_spearman_below_floor_no_current():
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.75, # below default floor of 0.8
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = None
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is False
    assert "spearman abaixo do floor" in decision.reason
    assert decision.triggered_metric == "spearman"

def test_drift_gate_spearman_regression_against_current():
    # Current has spearman of 0.9, cand has 0.83 (regression by 0.07, which is > margin 0.05)
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.83,
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = DriftReport(
        judge_label="Atual",
        spearman_composite=0.90,
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    thresholds = DriftThresholds() # floor 0.8, margin 0.05

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is False
    assert "regressao de ranking" in decision.reason
    assert decision.triggered_metric == "spearman"

def test_drift_gate_spearman_within_regression_margin():
    # Current has spearman of 0.9, cand has 0.88 (regression by 0.02, which is <= margin 0.05)
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.88,
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = DriftReport(
        judge_label="Atual",
        spearman_composite=0.90,
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is True
    assert "candidato nao regrediu" in decision.reason

def test_drift_gate_offset_above_alarm_no_current():
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.9,
        offset_scale=12.0, # above default offset_alarm of 10.0
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = None
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is False
    assert "inflacao de nota acima do alarme" in decision.reason
    assert decision.triggered_metric == "offset"

def test_drift_gate_offset_regression_against_current():
    # offset_scale is better when lower.
    # Current offset_scale = 4.0, cand = 7.5 (increase of 3.5, which is > margin 3.0)
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.9,
        offset_scale=7.5,
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = DriftReport(
        judge_label="Atual",
        spearman_composite=0.85,
        offset_scale=4.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    thresholds = DriftThresholds() # margin 3.0

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is False
    assert "inflacao de nota" in decision.reason
    assert decision.triggered_metric == "offset"

def test_drift_gate_offset_within_regression_margin():
    # Current offset_scale = 4.0, cand = 6.0 (increase of 2.0, which is <= margin 3.0)
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.9,
        offset_scale=6.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    atual = DriftReport(
        judge_label="Atual",
        spearman_composite=0.85,
        offset_scale=4.0,
        critical_rules_violated=False,
        low_confidence=False
    )
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is True

def test_drift_gate_low_confidence():
    # Accept with low confidence: accept=True but with specific message.
    cand = DriftReport(
        judge_label="Cand",
        spearman_composite=0.9,
        offset_scale=5.0,
        critical_rules_violated=False,
        low_confidence=True,
        mean_variance=12.5
    )
    atual = None
    thresholds = DriftThresholds()

    decision = DriftGate.avaliar_candidato(cand, atual, thresholds)
    assert decision.accept is True
    assert "candidato aceito com BAIXA CONFIANCA" in decision.reason
    assert decision.triggered_metric is None
