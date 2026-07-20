import pytest
from unittest.mock import patch, MagicMock
import sys
from types import ModuleType

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
        mock_emitter = MagicMock()
        mock_emitter.emit_log = MagicMock()
        mock_emitter.emit_node = MagicMock()
        mock_emitter.is_cancelled = MagicMock(return_value=False)
        
        mock_strategy_discoverer = MagicMock()
        mock_agent = MagicMock()
        mock_agent_cognitivo = MagicMock()
        mock_avaliador_modo_b = mock_heavy_evaluators['AvaliadorModoB']
        
        experience_store = ExperienceStore()
        bandit = MutationBandit()
        strategy_registry = StrategyRegistry()
        
        config = MCTSConfig(
            max_iterations=100,
            c_param=1.41,
            gamma=0.95,
            progressive_alpha=1.0,
            progressive_c=10.0,
            value_threshold=0.3,
            value_lr=0.1,
            bandit_c_param=1.41,
            bandit_temperature=2.0,
            bandit_temperature_decay=0.95,
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
            reward_floor=0.30,
        )
        
        final_config = overrides.get('config', config)
        final_emitter = overrides.get('emitter', mock_emitter)
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
            strategy_discoverer=final_strategy_discoverer,
            agent=final_agent,
            agent_cognitivo=final_agent_cognitivo,
            avaliador_modo_b=final_avaliador_modo_b,
            experience_store=final_experience_store,
            bandit=final_bandit,
            strategy_registry=final_strategy_registry,
        )
        
        return opt
    
    return _create_optimizer


class DeterministicJudge:
    """Juiz determinístico para experimentos de variância — isola ruído do LLM.

    Retorna rewards fixos por estratégia de mutação, permitindo medir
    a variância que vem exclusivamente do bandit e da ordem de expansão.
    """

    def __init__(self, strategy_rewards: dict = None):
        self._rewards = strategy_rewards or {}
        self._call_count = 0
        self._calls: list[dict] = []

    def set_reward(self, strategy_key: str, reward: float):
        self._rewards[strategy_key] = reward

    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str = ""):
        """Emula a interface do avaliador_modo_b.

        Determina a estratégia inferindo-a do conteúdo da skill_otimizada
        ou usa um fallback round-robin determinístico.
        """
        from src.signatures import AvaliacaoModoB

        self._call_count += 1
        idx = self._call_count

        # Tenta inferir a estratégia a partir de padrões no texto
        strategy = self._infer_strategy(skill_otimizada)
        reward = self._rewards.get(strategy, 0.50 + (idx * 0.03) % 0.20)

        self._calls.append({
            'call_num': idx,
            'inferred_strategy': strategy,
            'reward': reward,
            'skill_len': len(skill_otimizada),
        })

        defeitos = []
        if reward < 0.4:
            defeitos = ["Qualidade insuficiente — simulação determinística."]

        resultado = AvaliacaoModoB(
            manteve_regras_criticas=True,
            nota_clareza=reward * 100,
            nota_formatacao=reward * 100,
            nota_robustez=reward * 100,
            nota_densidade_informacional=reward * 100,
            nota_acionabilidade=reward * 100,
            nota_anti_fragilidade=reward * 100,
            feedback_detalhado=f'Deterministic judge: strategy={strategy}, reward={reward:.3f}',
            defeitos_encontrados=defeitos,
        )
        return resultado

    def _infer_strategy(self, text: str) -> str:
        """Infere a estratégia a partir de marcadores no texto."""
        normalized = text.lower()
        if '## raciocínio' in normalized and '## regras' in normalized:
            return 'mutador_cognitivo'
        if 'simplif' in normalized or 'simpler' in normalized:
            return 'simplificar'
        if 'exemplo' in normalized or 'example' in normalized:
            return 'adicionar_exemplos'
        if 'passo' in normalized or 'step' in normalized:
            return 'detalhar_passos'
        return 'default'

    def get_call_log(self) -> list[dict]:
        return list(self._calls)
