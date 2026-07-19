"""
Testes para teleprompter.py (Drift Gate behavior)

Cobertura:
- RN-07: Erro de medição → Fail-closed
- RN-08: Golden vazio → Fail-open
- Candidato aprovado → Persistido
- Candidato rejeitado → Descartado
"""

import pytest
from unittest.mock import MagicMock, patch
from src.teleprompter import _evaluate_drift_gate, _build_trainset
from src.experience_store import ExperienceStore, Experience


@pytest.fixture
def mock_golden_empty():
    """Mock de GoldenSet vazio para testar fail-open"""
    with patch('src.teleprompter.GoldenSet') as mock_gs:
        mock_instance = MagicMock()
        mock_instance.is_empty.return_value = True
        mock_gs.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_golden_with_data():
    """Mock de GoldenSet com dados para testar medição"""
    with patch('src.teleprompter.GoldenSet') as mock_gs:
        mock_instance = MagicMock()
        mock_instance.is_empty.return_value = False
        mock_gs.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_paths(tmp_path):
    """Cria paths temporários para testes"""
    candidate_path = tmp_path / "candidate.json"
    out_path = tmp_path / "out.json"
    output_dir = tmp_path
    
    candidate_path.write_text("{}")  # Criar arquivo vazio
    
    return candidate_path, out_path, output_dir


def test_drift_gate_fail_open_when_golden_empty(mock_golden_empty, mock_paths):
    """RN-08: Golden vazio → Fail-open (aceita candidato com warning)"""
    candidate_path, out_path, output_dir = mock_paths
    
    status = _evaluate_drift_gate(candidate_path, out_path, output_dir)
    
    assert status == "golden_empty_open"
    assert out_path.exists()  # Candidato foi movido para produção
    assert not candidate_path.exists()  # Candidato foi movido (não copiado)


def test_drift_gate_fail_closed_on_measurement_error(mock_golden_with_data, mock_paths):
    """RN-07: Erro de medição → Fail-closed (rejeita candidato)"""
    candidate_path, out_path, output_dir = mock_paths
    
    with patch('src.teleprompter.get_drift_thresholds') as mock_thresholds, \
         patch('src.teleprompter.DriftThresholds') as mock_dt, \
         patch('src.teleprompter.JudgeProbeRunner'), \
         patch('src.teleprompter.medir_drift') as mock_medir:
        
        mock_thresholds.return_value = {'repetitions': 3}
        mock_dt.from_config.return_value = MagicMock()
        
        # Simular erro na medição
        from src.drift.exceptions import DriftMeasurementError
        mock_medir.side_effect = DriftMeasurementError("Simulação de falha")
        
        status = _evaluate_drift_gate(candidate_path, out_path, output_dir)
        
        assert status == "measurement_error"
        assert not out_path.exists()  # Não foi movido para produção
        assert not candidate_path.exists()  # Candidato foi descartado


def test_drift_gate_accepts_candidate_below_threshold(mock_golden_with_data, mock_paths):
    """Candidato com drift aceitável → Aprovado e persistido"""
    candidate_path, out_path, output_dir = mock_paths
    
    with patch('src.teleprompter.get_drift_thresholds') as mock_thresholds, \
         patch('src.teleprompter.DriftThresholds') as mock_dt, \
         patch('src.teleprompter.JudgeProbeRunner'), \
         patch('src.teleprompter.medir_drift') as mock_medir, \
         patch('src.teleprompter.DriftGate') as mock_gate, \
         patch('src.teleprompter.load_drift_cache') as mock_load, \
         patch('src.teleprompter.save_drift_cache') as mock_save:
        
        mock_thresholds.return_value = {'repetitions': 3}
        mock_dt.from_config.return_value = MagicMock()
        
        # Mock relatório do candidato
        mock_report_cand = MagicMock()
        mock_report_cand.spearman_composite = 0.95
        mock_report_cand.offset_scale = 0.02
        mock_medir.return_value = mock_report_cand
        
        # Mock decisão positiva do gate
        mock_decision = MagicMock()
        mock_decision.accept = True
        mock_gate.avaliar_candidato.return_value = mock_decision
        
        mock_load.return_value = None
        
        status = _evaluate_drift_gate(candidate_path, out_path, output_dir)
        
        assert status == "compiled"
        assert out_path.exists()  # Candidato foi movido para produção
        assert not candidate_path.exists()  # Candidato foi movido
        mock_save.assert_called_once_with(mock_report_cand)


def test_drift_gate_rejects_candidate_above_threshold(mock_golden_with_data, mock_paths):
    """Candidato com drift excessivo → Rejeitado"""
    candidate_path, out_path, output_dir = mock_paths
    
    with patch('src.teleprompter.get_drift_thresholds') as mock_thresholds, \
         patch('src.teleprompter.DriftThresholds') as mock_dt, \
         patch('src.teleprompter.JudgeProbeRunner'), \
         patch('src.teleprompter.medir_drift') as mock_medir, \
         patch('src.teleprompter.DriftGate') as mock_gate, \
         patch('src.teleprompter.load_drift_cache') as mock_load:
        
        mock_thresholds.return_value = {'repetitions': 3}
        mock_dt.from_config.return_value = MagicMock()
        
        # Mock relatório do candidato
        mock_report_cand = MagicMock()
        mock_report_cand.spearman_composite = 0.50  # Drift excessivo
        mock_report_cand.offset_scale = 0.30
        mock_medir.return_value = mock_report_cand
        
        # Mock decisão negativa do gate
        mock_decision = MagicMock()
        mock_decision.accept = False
        mock_decision.reason = "Drift excessivo: spearman < 0.70"
        mock_gate.avaliar_candidato.return_value = mock_decision
        
        mock_load.return_value = None
        
        status = _evaluate_drift_gate(candidate_path, out_path, output_dir)
        
        assert status == "drift_rejected"
        assert not out_path.exists()  # Não foi movido para produção
        assert not candidate_path.exists()  # Candidato foi descartado


def test_build_trainset_filters_by_reward():
    """Testa que _build_trainset filtra experiências por min_reward"""
    store = ExperienceStore()
    store.experiences = []
    
    # Adicionar experiências com diferentes rewards
    store.add(Experience(
        skill_hash="hash1",
        mutation_strategy="strategy1",
        delta_reward=0.1,
        absolute_reward=0.9,  # Acima do threshold
        feedback="good",
        parent_instruction_hash="parent1",
        instruction="optimized1",
        parent_instruction="original1"
    ))
    
    store.add(Experience(
        skill_hash="hash2",
        mutation_strategy="strategy2",
        delta_reward=0.05,
        absolute_reward=0.5,  # Abaixo do threshold
        feedback="ok",
        parent_instruction_hash="parent2",
        instruction="optimized2",
        parent_instruction="original2"
    ))
    
    trainset = _build_trainset(store, min_reward=0.8)
    
    assert len(trainset) == 1
    assert trainset[0].skill_otimizada == "optimized1"


def test_build_trainset_empty_when_no_high_quality():
    """Testa que _build_trainset retorna lista vazia sem experiências de alta qualidade"""
    store = ExperienceStore()
    store.experiences = []
    
    store.add(Experience(
        skill_hash="hash1",
        mutation_strategy="strategy1",
        delta_reward=0.05,
        absolute_reward=0.5,  # Abaixo do threshold
        feedback="ok",
        parent_instruction_hash="parent1",
        instruction="optimized1",
        parent_instruction="original1"
    ))
    
    trainset = _build_trainset(store, min_reward=0.8)

    assert len(trainset) == 0


def test_compilar_avaliador_returns_no_data_when_lock_held():
    """Lock já ocupado → "no_data" (não bloqueia chamador)."""
    from src.teleprompter import compilar_avaliador, _compile_lock

    acquired = _compile_lock.acquire(blocking=False)
    assert acquired
    try:
        status = compilar_avaliador()
    finally:
        _compile_lock.release()

    assert status == "no_data"


def test_compilar_avaliador_returns_no_data_when_no_experiences():
    """ExperienceStore sem experiências de alta qualidade → "no_data"."""
    from src.teleprompter import compilar_avaliador

    mock_store = MagicMock()
    mock_store.experiences = []
    with patch('src.teleprompter.ExperienceStore', return_value=mock_store):
        status = compilar_avaliador()

    assert status == "no_data"


def test_compilar_avaliador_configures_lm_when_provided():
    """lm fornecido → dspy.settings.configure chamado antes da coleta de dados."""
    from src.teleprompter import compilar_avaliador

    mock_store = MagicMock()
    mock_store.experiences = []
    mock_lm = MagicMock()
    with patch('src.teleprompter.ExperienceStore', return_value=mock_store), \
         patch('src.teleprompter.dspy.settings') as mock_settings:
        status = compilar_avaliador(lm=mock_lm)

    assert status == "no_data"
    mock_settings.configure.assert_called_once_with(lm=mock_lm)


def test_drift_gate_backs_up_existing_out_path_on_accept(mock_golden_with_data, mock_paths):
    """Juiz atual presente (out_path existe) → snapshot .bak criado antes de persistir."""
    candidate_path, out_path, output_dir = mock_paths
    out_path.write_text('{"existing": true}')

    with patch('src.teleprompter.get_drift_thresholds') as mock_thresholds, \
         patch('src.teleprompter.DriftThresholds') as mock_dt, \
         patch('src.teleprompter.JudgeProbeRunner'), \
         patch('src.teleprompter.medir_drift') as mock_medir, \
         patch('src.teleprompter.DriftGate') as mock_gate, \
         patch('src.teleprompter.load_drift_cache') as mock_load, \
         patch('src.teleprompter.save_drift_cache'):

        mock_thresholds.return_value = {'repetitions': 3}
        mock_dt.from_config.return_value = MagicMock()
        mock_load.return_value = None

        mock_report_cand = MagicMock()
        mock_report_cand.spearman_composite = 0.95
        mock_report_cand.offset_scale = 0.02
        mock_medir.return_value = mock_report_cand

        mock_decision = MagicMock()
        mock_decision.accept = True
        mock_gate.avaliar_candidato.return_value = mock_decision

        status = _evaluate_drift_gate(candidate_path, out_path, output_dir)

    bak_path = output_dir / 'avaliador_modo_b_otimizado.json.bak'
    assert status == "compiled"
    assert out_path.exists()
    assert bak_path.exists()


def test_drift_gate_current_judge_measurement_failure_falls_back(mock_golden_with_data, mock_paths):
    """RN: falha ao medir juiz atual → floors absolutos (report_atual=None), candidato ainda avaliado."""
    from src.drift.exceptions import DriftMeasurementError

    candidate_path, out_path, output_dir = mock_paths
    out_path.write_text('{}')

    with patch('src.teleprompter.get_drift_thresholds') as mock_thresholds, \
         patch('src.teleprompter.DriftThresholds') as mock_dt, \
         patch('src.teleprompter.JudgeProbeRunner'), \
         patch('src.teleprompter.medir_drift') as mock_medir, \
         patch('src.teleprompter.DriftGate') as mock_gate, \
         patch('src.teleprompter.load_drift_cache') as mock_load, \
         patch('src.teleprompter.save_drift_cache'):

        mock_thresholds.return_value = {'repetitions': 3}
        mock_dt.from_config.return_value = MagicMock()
        mock_load.return_value = None

        mock_report_cand = MagicMock()
        mock_report_cand.spearman_composite = 0.95
        mock_report_cand.offset_scale = 0.02
        mock_medir.side_effect = [mock_report_cand, DriftMeasurementError("current judge failed")]

        mock_decision = MagicMock()
        mock_decision.accept = True
        mock_gate.avaliar_candidato.return_value = mock_decision

        status = _evaluate_drift_gate(candidate_path, out_path, output_dir)

    assert status == "compiled"
