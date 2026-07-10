import pytest
from unittest.mock import patch, MagicMock
import sys
from types import ModuleType

SRC_REPLACED = False
try:
    import src.ausculta_modo_b
except ImportError:
    # Only mock src.ausculta_modo_b, not the entire src package
    # (src.signatures or src.config may already be cached)
    ausculta_modo_b = ModuleType('ausculta_modo_b')
    sys.modules['src.ausculta_modo_b'] = ausculta_modo_b
    ausculta_modo_b.AvaliadorModoB = MagicMock()
    SRC_REPLACED = True

try:
    import sentence_transformers
except ImportError:
    sentence_transformers = ModuleType('sentence_transformers')
    sys.modules['sentence_transformers'] = sentence_transformers
    sentence_transformers.SentenceTransformer = MagicMock()

@pytest.fixture
def mock_heavy_evaluators():
    """Patches heavy evaluators to prevent real LLM and network calls in tests.

    Patch targets:
      - 'src.signatures.avaliador_modo_b_module': the global dspy.Predict instance
        that funcao_de_recompensa calls. Patching here intercepts all judge calls
        made by Optimizer.simulation() without touching DSPy internals.
      - 'src.semantic_evaluator.SentenceTransformer': patched at the module level
        because the name is bound at import time (module-level import), so patching
        the package-level name has no effect after first import.
    """
    mock_avaliador = MagicMock()
    mock_avaliador.return_value = MagicMock(
        manteve_regras_criticas='true',
        defeitos_encontrados='',
        nota_clareza='80',
        nota_formatacao='80',
        nota_robustez='80',
        nota_densidade_informacional='80',
        nota_acionabilidade='80',
        nota_anti_fragilidade='80',
        feedback_detalhado='Mock feedback.',
    )

    with patch('src.dspy_signatures.avaliador_modo_b_module', mock_avaliador), \
         patch('sentence_transformers.SentenceTransformer') as mock_st_pkg, \
         patch('src.semantic_evaluator.SentenceTransformer') as mock_st_module:
        mock_st_module.return_value = MagicMock()
        yield {
            'AvaliadorModoB': mock_avaliador,
            'SentenceTransformer': mock_st_module,
        }

@pytest.fixture
def sample_verbose_text():
    """Returns a large, highly verbose text string for testing Layer 2 readability penalties."""
    return "O gato senta no tapete macio e dorme bem. " * 30

@pytest.fixture
def sample_short_text():
    """Returns a short, direct text string for Layer 1 bypass testing."""
    return "Curto e direto. Poucas palavras."
