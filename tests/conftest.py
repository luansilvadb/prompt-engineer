import pytest
from unittest.mock import patch, MagicMock
import sys
from types import ModuleType

SRC_REPLACED = False
try:
    import src.ausculta_modo_b  # noqa: F401
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
    """Provides mocked heavy evaluators so tests avoid real LLM/network calls.

    The configured AvaliacaoModoB result is reused by mock_optimizer_factory as the
    Optimizer's avaliador_modo_b, so simulation() returns a deterministic numeric
    score instead of a bare MagicMock (whose nota attributes break calcular_composite).
    SentenceTransformer is patched at import-bound locations to short-circuit the
    semantic evaluator.
    """
    from src.signatures import AvaliacaoModoB

    mock_resultado = AvaliacaoModoB(
        manteve_regras_criticas=True,
        nota_clareza=80.0,
        nota_formatacao=80.0,
        nota_robustez=80.0,
        nota_densidade_informacional=80.0,
        nota_acionabilidade=80.0,
        nota_anti_fragilidade=80.0,
        feedback_detalhado='Mock feedback.',
        defeitos_encontrados=[],
    )
    mock_avaliador = MagicMock(return_value=mock_resultado)

    with patch('src.infrastructure.dspy_impl.DSPyAvaliadorModoB', mock_avaliador), \
         patch('sentence_transformers.SentenceTransformer'), \
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


@pytest.fixture
def mock_optimizer_factory(mock_heavy_evaluators):
    """Factory fixture that creates a fully configured Optimizer with all dependencies mocked."""
    from src.optimizer import Optimizer
    from src.domain.config import MCTSConfig
    from src.mutation_strategies.bandit import MutationBandit
    from src.mutation_strategies.registry import StrategyRegistry
    from src.experience_store import ExperienceStore
    
    def _create_optimizer(skill_original: str = "Test", **overrides):
        """
        Create an Optimizer with sensible defaults for testing.
        
        Args:
            skill_original: The original skill text
            **overrides: Override any default mock or config value
        """
        # Create default mocks
        mock_emitter = MagicMock()
        mock_emitter.emit_log = MagicMock()
        mock_emitter.emit_node = MagicMock()
        mock_emitter.is_cancelled = MagicMock(return_value=False)
        
        mock_scoring_pipeline = MagicMock()
        mock_scoring_pipeline.run = MagicMock(return_value=MagicMock(final_score=0.8))
        
        mock_strategy_discoverer = MagicMock()
        mock_agent = MagicMock()
        mock_agent_cognitivo = MagicMock()
        mock_avaliador_modo_b = mock_heavy_evaluators['AvaliadorModoB']
        
        # Create real instances with proper initialization
        experience_store = ExperienceStore()
        bandit = MutationBandit()
        strategy_registry = StrategyRegistry()
        
        # Default config
        config = MCTSConfig(
            max_iterations=100,
            c_param=1.41,
            gamma=0.95,
            progressive_alpha=1.0,
            progressive_c=10.0,
            value_threshold=0.3,
            value_lr=0.1,
            bandit_c_param=1.41,
            semantic_sim_threshold=0.92,
            lexical_density_min=0.35,
            verbosity_penalty_factor=0.7,
            buzzword_threshold=3,
            cognitivo_prior_count=2,
            cognitivo_prior_mean_delta=0.05,
            density_threshold=0.9,
            density_multiplier_min=0.8,
            density_multiplier_max=1.2,
            density_structured_bonus=0.05,
        )
        
        # Apply overrides
        final_config = overrides.get('config', config)
        final_emitter = overrides.get('emitter', mock_emitter)
        final_scoring_pipeline = overrides.get('scoring_pipeline', mock_scoring_pipeline)
        final_strategy_discoverer = overrides.get('strategy_discoverer', mock_strategy_discoverer)
        final_agent = overrides.get('agent', mock_agent)
        final_agent_cognitivo = overrides.get('agent_cognitivo', mock_agent_cognitivo)
        final_avaliador_modo_b = overrides.get('avaliador_modo_b', mock_avaliador_modo_b)
        final_experience_store = overrides.get('experience_store', experience_store)
        final_bandit = overrides.get('bandit', bandit)
        final_strategy_registry = overrides.get('strategy_registry', strategy_registry)
        
        opt = Optimizer(
            skill_original=skill_original,
            config=final_config,
            emitter=final_emitter,
            scoring_pipeline=final_scoring_pipeline,
            strategy_discoverer=final_strategy_discoverer,
            agent=final_agent,
            agent_cognitivo=final_agent_cognitivo,
            avaliador_modo_b=final_avaliador_modo_b,
            experience_store=final_experience_store,
            bandit=final_bandit,
            strategy_registry=final_strategy_registry,
        )
        
        # Add is_cancelled method that delegates to emitter
        opt.is_cancelled = final_emitter.is_cancelled
        
        return opt
    
    return _create_optimizer
