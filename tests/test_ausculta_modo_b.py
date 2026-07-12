"""
Testes para ausculta_modo_b.py (Structural validation)

Cobertura:
- Skill com regras estruturais válidas → Aceita
- Skill sem seções obrigatórias → Rejeita
- Skill com regras críticas violadas → Rejeita
"""

import pytest
from unittest.mock import MagicMock, patch
from src.drift.models import GoldenProbe, ProbeExpectation


@pytest.fixture
def mock_setup():
    """Mock da função setup para evitar configuração real de LLM"""
    with patch('src.ausculta_modo_b.setup') as mock:
        yield mock


@pytest.fixture
def mock_runner():
    """Mock do JudgeProbeRunner"""
    with patch('src.ausculta_modo_b.JudgeProbeRunner') as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


def test_ausculta_accepts_valid_skill(mock_setup, mock_runner):
    """Skill com regras estruturais válidas → Aceita (score alto)"""
    from src.ausculta_modo_b import auscultar_modo_b
    
    # Mock do relatório de drift com score alto
    mock_report = MagicMock()
    mock_report.spearman_composite = 0.95
    mock_report.offset_scale = 0.02
    mock_report.per_probe = [{
        'probe_id': 'probe-espelho-distorcido-01',
        'predicted_composite': 0.70,  # Score baixo para passar na validação de penalização
        'expected_composite': 0.80,
        'observed_critical_all_correct': True
    }]
    
    with patch('src.ausculta_modo_b.medir_drift', return_value=mock_report), \
         patch('src.ausculta_modo_b.Path') as mock_path:
        
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance
        
        # Não deve lançar exceção ou chamar sys.exit
        auscultar_modo_b()
        
        # Verifica que o runner foi configurado
        mock_runner.as_zero_modo_b.assert_called_once()


def test_ausculta_rejects_skill_violating_critical_rules(mock_setup, mock_runner):
    """Skill com regras críticas violadas → Rejeita (score baixo + sys.exit)"""
    from src.ausculta_modo_b import auscultar_modo_b
    
    # Mock do relatório de drift com score baixo (contradição detectada)
    mock_report = MagicMock()
    mock_report.spearman_composite = 0.60
    mock_report.offset_scale = 0.15
    mock_report.per_probe = [{
        'probe_id': 'probe-espelho-distorcido-01',
        'predicted_composite': 0.80,  # Score alto mas não detectou contradição
        'expected_composite': 0.665,
        'observed_critical_all_correct': False  # Violação de regras críticas
    }]
    
    with patch('src.ausculta_modo_b.medir_drift', return_value=mock_report), \
         patch('src.ausculta_modo_b.Path') as mock_path, \
         patch('src.ausculta_modo_b.sys.exit') as mock_exit:
        
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance
        
        auscultar_modo_b()
        
        # Verifica que sys.exit(1) foi chamado (skill rejeitada)
        mock_exit.assert_called_once_with(1)


def test_ausculta_handles_measurement_error(mock_setup, mock_runner):
    """Erro durante medição → Propaga exceção e chama sys.exit"""
    from src.ausculta_modo_b import auscultar_modo_b
    
    with patch('src.ausculta_modo_b.medir_drift') as mock_medir, \
         patch('src.ausculta_modo_b.Path') as mock_path, \
         patch('src.ausculta_modo_b.sys.exit') as mock_exit:
        
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance
        
        # Simular erro na medição
        mock_medir.side_effect = Exception("Simulação de falha na medição")
        
        auscultar_modo_b()
        
        # Verifica que sys.exit(1) foi chamado (erro tratado)
        mock_exit.assert_called_once_with(1)


def test_ausculta_loads_existing_model(mock_setup, mock_runner):
    """Testa que o modelo existente é carregado quando disponível"""
    from src.ausculta_modo_b import auscultar_modo_b
    
    mock_report = MagicMock()
    mock_report.spearman_composite = 0.95
    mock_report.offset_scale = 0.02
    mock_report.per_probe = [{
        'probe_id': 'probe-espelho-distorcido-01',
        'predicted_composite': 0.70,
        'expected_composite': 0.665,
        'observed_critical_all_correct': True
    }]
    
    with patch('src.ausculta_modo_b.medir_drift', return_value=mock_report), \
         patch('src.ausculta_modo_b.Path') as mock_path:
        
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True  # Modelo existe
        mock_path.return_value = mock_path_instance
        
        auscultar_modo_b()
        
        # Verifica que load_candidate_modo_b foi chamado
        mock_runner.load_candidate_modo_b.assert_called_once()
        mock_runner.as_zero_modo_b.assert_not_called()


def test_golden_probe_structure():
    """Testa a estrutura de um GoldenProbe válido"""
    expectations = ProbeExpectation(
        manteve_regras_criticas=False,
        nota_clareza=80.0,
        nota_formatacao=90.0,
        nota_robustez=60.0,
        nota_densidade_informacional=70.0,
        nota_acionabilidade=50.0,
        nota_anti_fragilidade=60.0
    )
    
    probe = GoldenProbe(
        id="test-probe",
        skill_original="Original skill",
        skill_otimizada="Optimized skill",
        regras_adicionais="Additional rules",
        expected=expectations,
        expected_rank_band='fail',
        verifier="Test-Verifier"
    )
    
    assert probe.id == "test-probe"
    assert probe.expected.nota_clareza == 80.0
    assert probe.expected_rank_band == 'fail'
    assert probe.verifier == "Test-Verifier"
