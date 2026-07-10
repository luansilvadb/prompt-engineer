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
    """Patches heavy evaluators like AvaliadorModoB and SentenceTransformer to prevent network calls."""
    with patch('src.ausculta_modo_b.AvaliadorModoB') as mock_avaliador, \
         patch('sentence_transformers.SentenceTransformer') as mock_sentence_transformer:
        yield {
            'AvaliadorModoB': mock_avaliador,
            'SentenceTransformer': mock_sentence_transformer
        }

@pytest.fixture
def sample_verbose_text():
    """Returns a large, highly verbose text string for testing Layer 2 readability penalties."""
    return "O gato senta no tapete macio e dorme bem. " * 30

@pytest.fixture
def sample_short_text():
    """Returns a short, direct text string for Layer 1 bypass testing."""
    return "Curto e direto. Poucas palavras."
