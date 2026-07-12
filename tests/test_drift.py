import pytest
from unittest.mock import MagicMock, patch
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import (
    ProbeExpectation,
    GoldenProbe,
    ProbeMeasurement,
    DriftThresholds
)
from src.drift.golden import GoldenSet
from src.drift.metrics import (
    _compute_ranks,
    _spearman_rank_correlation,
    medir_drift
)
from src.drift.runner import JudgeProbeRunner
from src.signatures import Avaliacao, AvaliacaoModoB

def test_spearman_rank_correlation_edge_cases():
    # n < 2 should return 1.0
    assert _spearman_rank_correlation([1.0], [1.0]) == 1.0
    assert _spearman_rank_correlation([], []) == 1.0

    # Perfect positive correlation
    assert _spearman_rank_correlation([1, 2, 3], [10, 20, 30]) == 1.0

    # Perfect negative correlation
    assert _spearman_rank_correlation([1, 2, 3], [30, 20, 10]) == -1.0

    # Simple ties check
    # ranks of x=[1, 2, 2] -> [1.0, 2.5, 2.5]
    # ranks of y=[2, 2, 3] -> [1.5, 1.5, 3.0]
    ranks_x = _compute_ranks([1, 2, 2])
    assert ranks_x == [1.0, 2.5, 2.5]

    val = _spearman_rank_correlation([1, 2, 2], [2, 2, 3])
    # rx = [1.0, 2.5, 2.5], ry = [1.5, 1.5, 3.0]
    # d = [-0.5, 1.0, -0.5], d^2 = [0.25, 1.0, 0.25], sum(d^2) = 1.5
    # spearman = 1 - (6 * 1.5) / (3 * 8) = 1 - 9 / 24 = 1 - 0.375 = 0.625
    assert pytest.approx(val) == 0.625

def test_probe_expectation_composite():
    exp = ProbeExpectation(
        manteve_regras_criticas=True,
        nota_clareza=80.0,
        nota_formatacao=90.0,
        nota_robustez=70.0,
        nota_densidade_informacional=60.0,
        nota_acionabilidade=80.0,
        nota_anti_fragilidade=50.0
    )
    # Total score should be calculated correctly via calcular_composite
    score = exp.composite_score()
    assert 0.0 <= score <= 1.0

def test_probe_measurement():
    av1 = Avaliacao(
        manteve_regras_criticas=True,
        nota_clareza=80,
        nota_formatacao=80,
        nota_robustez=80,
        nota_densidade_informacional=80,
        nota_acionabilidade=80,
        nota_anti_fragilidade=80,
        feedback_detalhado="f1"
    )
    av2 = Avaliacao(
        manteve_regras_criticas=True,
        nota_clareza=90,
        nota_formatacao=90,
        nota_robustez=90,
        nota_densidade_informacional=90,
        nota_acionabilidade=90,
        nota_anti_fragilidade=90,
        feedback_detalhado="f2"
    )

    measurement = ProbeMeasurement(probe_id="p1", samples=[av1, av2])

    # mean_composite should calculate average
    assert 0.8 <= measurement.mean_composite() <= 0.9

    # mean_per_dimension should average correctly
    dims = measurement.mean_per_dimension()
    assert dims["nota_clareza"] == 85.0
    assert dims["nota_formatacao"] == 85.0

    # variance check
    assert measurement.variance() > 0.0

def test_critical_rules_violations():
    # Probe that should NOT violate critical rules (expected=True)
    av_ok = Avaliacao(
        manteve_regras_criticas=True,
        nota_clareza=80,
        nota_formatacao=80,
        nota_robustez=80,
        nota_densidade_informacional=80,
        nota_acionabilidade=80,
        nota_anti_fragilidade=80,
        feedback_detalhado=""
    )
    av_fail = Avaliacao(
        manteve_regras_criticas=False,
        nota_clareza=80,
        nota_formatacao=80,
        nota_robustez=80,
        nota_densidade_informacional=80,
        nota_acionabilidade=80,
        nota_anti_fragilidade=80,
        feedback_detalhado=""
    )

    # Case 1: Expected rules kept (True). Juice says both True
    m1 = ProbeMeasurement(probe_id="p1", samples=[av_ok, av_ok])
    assert m1.critical_rules_all_correct(True) is True
    assert m1.missed_violation_count(True) == 0
    assert m1.false_rejection_count(True) == 0

    # Case 2: Expected rules kept (True). Juice says one False (false rejection)
    m2 = ProbeMeasurement(probe_id="p2", samples=[av_ok, av_fail])
    assert m2.critical_rules_all_correct(True) is False
    assert m2.missed_violation_count(True) == 0
    assert m2.false_rejection_count(True) == 1

    # Case 3: Expected rules violated (False). Juice says one True (missed violation / security flaw)
    m3 = ProbeMeasurement(probe_id="p3", samples=[av_fail, av_ok])
    assert m3.critical_rules_all_correct(False) is False
    assert m3.missed_violation_count(False) == 1
    assert m3.false_rejection_count(False) == 0

def test_medir_drift_empty_golden():
    runner = MagicMock()
    golden = GoldenSet()
    # Explicitly clear probes to bypass files that might be loaded from disk
    golden.probes = []
    thresholds = DriftThresholds()

    with pytest.raises(DriftMeasurementError, match="Golden set vazio"):
        medir_drift(runner, golden, 3, thresholds)

def test_medir_drift_success():
    # Setup mock runner
    runner = MagicMock()
    runner.label = "TestRunner"

    # Golden Set with 2 probes
    exp1 = ProbeExpectation(
        manteve_regras_criticas=True,
        nota_clareza=80.0,
        nota_formatacao=80.0,
        nota_robustez=80.0,
        nota_densidade_informacional=80.0,
        nota_acionabilidade=80.0,
        nota_anti_fragilidade=80.0
    )
    p1 = GoldenProbe("p1", "orig1", "opt1", "rules1", exp1, "alto", "v1")

    exp2 = ProbeExpectation(
        manteve_regras_criticas=False,
        nota_clareza=50.0,
        nota_formatacao=50.0,
        nota_robustez=50.0,
        nota_densidade_informacional=50.0,
        nota_acionabilidade=50.0,
        nota_anti_fragilidade=50.0
    )
    p2 = GoldenProbe("p2", "orig2", "opt2", "rules2", exp2, "baixo", "v2")

    golden = GoldenSet()
    golden.probes = [p1, p2]

    # Mock runner behavior: return measurements
    av_p1 = Avaliacao(
        manteve_regras_criticas=True,
        nota_clareza=82,
        nota_formatacao=82,
        nota_robustez=82,
        nota_densidade_informacional=82,
        nota_acionabilidade=82,
        nota_anti_fragilidade=82,
        feedback_detalhado=""
    )
    av_p2 = Avaliacao(
        manteve_regras_criticas=False,
        nota_clareza=55,
        nota_formatacao=55,
        nota_robustez=55,
        nota_densidade_informacional=55,
        nota_acionabilidade=55,
        nota_anti_fragilidade=55,
        feedback_detalhado=""
    )

    m1 = ProbeMeasurement("p1", [av_p1])
    m2 = ProbeMeasurement("p2", [av_p2])

    runner.run.side_effect = lambda probe, reps: m1 if probe.id == "p1" else m2

    thresholds = DriftThresholds(variance_low_confidence=8.0)

    report = medir_drift(runner, golden, 1, thresholds)

    assert report.judge_label == "TestRunner"
    assert report.spearman_composite == 1.0 # perfect ranking matching
    # mean predicted is roughly 0.685, mean expected is 0.65 -> positive offset_scale
    assert report.offset_scale > 0
    assert report.critical_rules_violated is False
    assert report.missed_violations == 0
    assert report.false_rejections == 0
    assert report.low_confidence is False

@patch("src.drift.runner._invoke_judge_with")
@patch("src.drift.runner._invoke_judge_modo_b_with")
def test_judge_probe_runner(mock_invoke_b, mock_invoke_a):
    runner = JudgeProbeRunner(label="MyRunner")

    # Mocking standard prediction outputs
    av_a = Avaliacao(
        manteve_regras_criticas=True,
        nota_clareza=90,
        nota_formatacao=90,
        nota_robustez=90,
        nota_densidade_informacional=90,
        nota_acionabilidade=90,
        nota_anti_fragilidade=90,
        feedback_detalhado="ok A"
    )
    mock_invoke_a.return_value = av_a

    av_b = AvaliacaoModoB(
        manteve_regras_criticas=False,
        defeitos_encontrados=["Defect 1"],
        nota_clareza=40,
        nota_formatacao=40,
        nota_robustez=40,
        nota_densidade_informacional=40,
        nota_acionabilidade=40,
        nota_anti_fragilidade=40,
        feedback_detalhado="ok B"
    )
    mock_invoke_b.return_value = av_b

    # Mock golden probe
    exp = ProbeExpectation(True, 80, 80, 80, 80, 80, 80)
    probe = GoldenProbe("p1", "orig", "opt", "rules", exp, "alto", "v")

    # Run modo A
    m_a = runner.run(probe, repetitions=2, modo='a')
    assert len(m_a.samples) == 2
    assert m_a.samples[0].feedback_detalhado == "ok A"
    assert m_a.samples[0].manteve_regras_criticas is True

    # Run modo B
    m_b = runner.run(probe, repetitions=2, modo='b')
    assert len(m_b.samples) == 2
    assert m_b.samples[0].feedback_detalhado == "ok B"
    assert m_b.samples[0].manteve_regras_criticas is False
    assert m_b.samples[0].defeitos_encontrados == ["Defect 1"]

    # ValueError on unknown mode
    with pytest.raises(ValueError, match="Modo desconhecido"):
        runner.run(probe, repetitions=1, modo='c')

    # DriftMeasurementError when all reps fail
    mock_invoke_a.side_effect = Exception("DSPy Error")
    with pytest.raises(DriftMeasurementError, match="Todas as 2 repetições falharam"):
        runner.run(probe, repetitions=2, modo='a')
