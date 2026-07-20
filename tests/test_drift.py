import pytest
import json
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

    def _run_side_effect(probe, reps):
        return m1 if probe.id == "p1" else m2

    # _measure_all_probes agora usa runner.clone() para paralelismo.
    # O clone deve retornar um mock cujo .run() tenha o mesmo side_effect.
    cloned_mock = MagicMock()
    cloned_mock.run.side_effect = _run_side_effect
    runner.clone.return_value = cloned_mock

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


# ---------------------------------------------------------------------------
# GoldenSet persistence + JudgeProbeRunner error paths — previously uncovered.
# Contratos sob teste:
#   - GoldenSet._parse_golden_json / save: round-trip atômico (BR3 curadoria)
#   - GoldenSet._load: fail-open (golden ausente) e resiliência a JSON inválido
#   - JudgeProbeRunner.load_candidate(_modo_b): fail-closed em erro de carga
#   - JudgeProbeRunner.as_zero(_modo_b): reinicializa juiz p/ baseline zero
# ---------------------------------------------------------------------------


def _make_probe(pid="p1", rank="alto", verifier="v1"):
    exp = ProbeExpectation(
        manteve_regras_criticas=True,
        nota_clareza=80.0, nota_formatacao=80.0, nota_robustez=80.0,
        nota_densidade_informacional=80.0, nota_acionabilidade=80.0,
        nota_anti_fragilidade=80.0,
    )
    return GoldenProbe(
        id=pid, skill_original="orig", skill_otimizada="opt",
        regras_adicionais="rules", expected=exp,
        expected_rank_band=rank, verifier=verifier,
    )


@patch('src.drift.golden.GOLDEN_DIR', None)
def test_golden_set_parse_save_round_trip(tmp_path):
    """save() escreve JSON atômico e _load() reconstitui probes idênticos (BR3)."""
    golden_dir = tmp_path / 'golden'
    with patch('src.drift.golden.GOLDEN_DIR', golden_dir):
        gs = GoldenSet()  # não há arquivo → probes=[]
        assert gs.is_empty()

        gs.probes = [_make_probe('p1', 'alto', 'v1'), _make_probe('p2', 'baixo', 'v2')]
        gs.save(version='1.2.0', curated_at='2026-07-12T00:00:00Z')

        # O arquivo persistido existe e é JSON válido.
        stored = golden_dir / 'golden_set.json'
        assert stored.exists()
        data = json.loads(stored.read_text(encoding='utf-8'))
        assert data['version'] == '1.2.0'
        assert data['curated_at'] == '2026-07-12T00:00:00Z'
        assert len(data['probes']) == 2

        # Nova instância carrega o mesmo conteúdo.
        reloaded = GoldenSet()
        assert reloaded.version == '1.2.0'
        assert len(reloaded.probes) == 2
        assert {p.id for p in reloaded.probes} == {'p1', 'p2'}
        first = reloaded.probes[0]
        assert first.expected.nota_clareza == 80.0
        assert first.expected_rank_band in ('alto', 'baixo')


@patch('src.drift.golden.GOLDEN_DIR', None)
def test_golden_set_parse_handles_missing_optional_fields(tmp_path):
    """_parse_golden_json aceita probes sem regras_adicionais/verifier (defaults)."""
    golden_dir = tmp_path / 'golden'
    payload = {
        'version': '1.0.0', 'curated_at': 'now',
        'probes': [{
            'id': 'px', 'skill_original': 'o', 'skill_otimizada': 'p',
            'expected': {
                'manteve_regras_criticas': True, 'nota_clareza': 70,
                'nota_formatacao': 70, 'nota_robustez': 70,
                'nota_densidade_informacional': 70, 'nota_acionabilidade': 70,
                'nota_anti_fragilidade': 70,
            },
            'expected_rank_band': 'medio',
            # regras_adicionais e verifier omitidos proposicalmente
        }],
    }
    with patch('src.drift.golden.GOLDEN_DIR', golden_dir):
        (golden_dir).mkdir(parents=True, exist_ok=True)
        (golden_dir / 'golden_set.json').write_text(json.dumps(payload), encoding='utf-8')
        gs = GoldenSet()

    assert len(gs.probes) == 1
    probe = gs.probes[0]
    assert probe.regras_adicionais == ''   # default .get('')
    assert probe.verifier == ''            # default .get('')
    assert probe.id == 'px'


@patch('src.drift.golden.GOLDEN_DIR', None)
def test_golden_set_load_malformed_json_falls_back_to_empty(tmp_path):
    """JSON corrompido → fail-open: probes=[] sem lançar (mensagem de aviso via logger)."""
    from loguru import logger
    import io
    golden_dir = tmp_path / 'golden'
    golden_dir.mkdir(parents=True, exist_ok=True)
    (golden_dir / 'golden_set.json').write_text('{ NOT VALID JSON !!!', encoding='utf-8')
    log_output = io.StringIO()
    sink_id = logger.add(log_output, format="{message}")
    try:
        with patch('src.drift.golden.GOLDEN_DIR', golden_dir):
            gs = GoldenSet()
    finally:
        logger.remove(sink_id)
    assert gs.probes == []
    assert gs.is_empty()
    assert 'Erro ao carregar golden set' in log_output.getvalue()


@patch('src.drift.golden.GOLDEN_DIR', None)
def test_golden_set_load_missing_file_is_empty_fail_open(tmp_path):
    """Arquivo ausente → fail-open (probes=[]), mensagem explícita via logger."""
    from loguru import logger
    import io
    log_output = io.StringIO()
    sink_id = logger.add(log_output, format="{message}")
    try:
        with patch('src.drift.golden.GOLDEN_DIR', tmp_path / 'absent'):
            gs = GoldenSet()
    finally:
        logger.remove(sink_id)
    assert gs.is_empty()
    assert 'Golden set ausente' in log_output.getvalue()


# --- JudgeProbeRunner error paths ------------------------------------------


def test_runner_load_candidate_raises_on_failure():
    """Falha ao carregar few-shot do candidato (Modo A) → DriftMeasurementError."""
    runner = JudgeProbeRunner(label="cand")
    with patch.object(runner._judge, 'load', side_effect=FileNotFoundError("no file")):
        with pytest.raises(DriftMeasurementError, match="Falha ao carregar juiz candidato"):
            runner.load_candidate('/path/to/cand.json')


def test_runner_load_candidate_modo_b_raises_on_failure():
    """Falha ao carregar few-shot do candidato (Modo B) → DriftMeasurementError."""
    runner = JudgeProbeRunner(label="cand")
    with patch.object(runner._judge_modo_b, 'load', side_effect=OSError("corrupt")):
        with pytest.raises(DriftMeasurementError, match="Modo B"):
            runner.load_candidate_modo_b('/path/to/cand_b.json')


def test_runner_load_candidate_error_preserves_context():
    """DriftMeasurementError carrega contexto diagnóstico (label/path/original)."""
    runner = JudgeProbeRunner(label="meu_juiz")
    with patch.object(runner._judge, 'load', side_effect=RuntimeError("bad demo")):
        with pytest.raises(DriftMeasurementError) as exc_info:
            runner.load_candidate('/x/y.json')
    ctx = exc_info.value.context
    assert ctx['judge_label'] == 'meu_juiz'
    assert ctx['path'] == '/x/y.json'
    assert 'bad demo' in ctx['original']


def test_runner_as_zero_replaces_modoa_judge():
    """as_zero() reinicializa o juiz Modo A (baseline de drift-zero)."""
    runner = JudgeProbeRunner(label="z")
    original = runner._judge
    runner.as_zero()
    assert runner._judge is not original  # nova instância zerada


def test_runner_as_zero_modo_b_replaces_modob_judge():
    """as_zero_modo_b() reinicializa o juiz Modo B."""
    runner = JudgeProbeRunner(label="z")
    original = runner._judge_modo_b
    runner.as_zero_modo_b()
    assert runner._judge_modo_b is not original


def test_runner_run_modo_b_partial_failure_still_returns_samples():
    """run_modo_b tolera falhas parciais: retorna samples das reps bem-sucedidas."""
    runner = JudgeProbeRunner(label="partial")
    ok = AvaliacaoModoB(
        manteve_regras_criticas=True, nota_clareza=80, nota_formatacao=80,
        nota_robustez=80, nota_densidade_informacional=80, nota_acionabilidade=80,
        nota_anti_fragilidade=80, feedback_detalhado="ok", defeitos_encontrados=[],
    )
    # 1a rep OK, 2a rep falha.
    with patch('src.drift.runner._invoke_judge_modo_b_with', side_effect=[ok, Exception("boom")]):
        probe = _make_probe()
        measurement = runner.run_modo_b(probe, repetitions=2)
    assert len(measurement.samples) == 1
    assert measurement.samples[0].feedback_detalhado == "ok"


def test_runner_run_modo_b_all_fail_raises():
    """run_modo_b: todas as reps falhando → DriftMeasurementError (Modo B)."""
    runner = JudgeProbeRunner(label="allfail")
    with patch('src.drift.runner._invoke_judge_modo_b_with', side_effect=Exception("down")):
        with pytest.raises(DriftMeasurementError, match="Modo B"):
            runner.run_modo_b(_make_probe(), repetitions=2)


# ---------------------------------------------------------------------------
# Testes de regressao para _parse_manteve_regras — Item 2 (hard-gate SD-2)
# ---------------------------------------------------------------------------

from src.infrastructure.dspy_impl import _parse_manteve_regras


@pytest.mark.parametrize("input_val,expected", [
    # True cases
    ("True", True),
    ("true", True),
    ("TRUE", True),
    ("True.", True),
    ("true, com ressalvas", True),
    ("sim", True),
    ("Sim", True),
    ("SIM", True),
    ("yes", True),
    ("Yes", True),
    ("YES", True),
    ("1", True),
    # False cases
    ("False", False),
    ("false", False),
    ("FALSE", False),
    ("false, a lei foi removida", False),
    ("não", False),
    ("nao", False),
    ("no", False),
    ("0", False),
    # Edge cases
    ("", False),
    (None, False),
    ("maybe", False),
    ("parcialmente", False),
    ("   true   ", True),
    ("   false   ", False),
    # Case: "0" should NOT match (it's not in true_markers)
    ("0", False),
    # Case: "True-ish" text
    ("not true", False),  # 'not true' starts with 'no' → false_markers catches it
    ("untrue", False),    # 'untrue' doesn't start with false_markers, but doesn't contain true_markers
])
def test_parse_manteve_regras_edge_cases(input_val, expected):
    """Item 2: _parse_manteve_regras deve lidar com todos os edge cases corretamente."""
    assert _parse_manteve_regras(input_val) == expected


def test_missed_violation_sd2_scenario():
    """
    Item 2 — Regressao: simulacao exata do cenario SD-2.

    SD-2: expected_critical=False (skill viola Lei de Ferro).
    Se o juiz retornar manteve_regras_criticas=True, missed_violation_count
    deve contar como violacao nao detectada.
    """
    # Simula 3 repeticoes do juiz: 2 dizem True (errado), 1 diz False (certo)
    av_good = Avaliacao(
        manteve_regras_criticas=False,  # juiz acertou: detectou violacao
        nota_clareza=70, nota_formatacao=75, nota_robustez=40,
        nota_densidade_informacional=60, nota_acionabilidade=55,
        nota_anti_fragilidade=35, feedback_detalhado=""
    )
    av_bad1 = Avaliacao(
        manteve_regras_criticas=True,  # juiz errou: nao detectou violacao
        nota_clareza=80, nota_formatacao=80, nota_robustez=80,
        nota_densidade_informacional=80, nota_acionabilidade=80,
        nota_anti_fragilidade=80, feedback_detalhado=""
    )
    av_bad2 = Avaliacao(
        manteve_regras_criticas=True,  # juiz errou novamente
        nota_clareza=85, nota_formatacao=85, nota_robustez=85,
        nota_densidade_informacional=85, nota_acionabilidade=85,
        nota_anti_fragilidade=85, feedback_detalhado=""
    )

    # expected_critical=False porque SD-2 e uma violacao
    measurement = ProbeMeasurement(probe_id="SD-2", samples=[av_bad1, av_bad2, av_good])

    # critical_rules_all_correct: TODAS devem concordar → False (2 das 3 estao erradas)
    assert measurement.critical_rules_all_correct(False) is False

    # missed_violation_count: esperado=False, juiz disse True → 2 violacoes nao detectadas
    assert measurement.missed_violation_count(False) == 2

    # false_rejection_count: esperado=False → nunca conta (so conta quando esperado=True)
    assert measurement.false_rejection_count(False) == 0
