from unittest.mock import MagicMock
from src.domain.mcts import MCTSNode, TranspositionTable
from src.optimizer import Optimizer
from src.domain.config import load_mcts_config
from src.infrastructure.events import JobEventEmitter

def test_transposition_table_basic():
    tt = TranspositionTable()
    node = MCTSNode(instruction="test instruction")
    node.q_value = 5.0
    node.visits = 2
    node.feedback = "Good quality"
    
    assert tt.hits == 0
    assert not tt.contains("key1")
    
    saved = tt.put("key1", node)
    assert saved == node
    assert tt.contains("key1")
    
    retrieved = tt.get("key1")
    assert retrieved == node
    assert tt.hits == 1

def test_transposition_table_normalization():
    tt = TranspositionTable()
    node = MCTSNode(instruction="test instruction")
    
    # Inserir com quebra de linha Windows e espaços
    tt.put("  instrucao com espacos \r\n ", node)
    
    # Recuperar com quebra Unix e sem espaços extras
    retrieved = tt.get("instrucao com espacos")
    assert retrieved == node
    assert tt.hits == 1

def test_early_heuristic_cut_off():
    emitter = JobEventEmitter()
    config = load_mcts_config()
    mock_agent = MagicMock()
    mock_agent_cog = MagicMock()
    mock_eval = MagicMock()
    mock_store = MagicMock()
    mock_store.get_strategy_stats.return_value = {}
    mock_bandit = MagicMock()
    mock_registry = MagicMock()
    mock_registry.get_all_keys.return_value = []
    
    optimizer = Optimizer(
        skill_original="Skill original detalhada com bastante contexto.",
        config=config,
        emitter=emitter,
        strategy_discoverer=MagicMock(),
        agent=mock_agent,
        agent_cognitivo=mock_agent_cog,
        avaliador_modo_b=mock_eval,
        experience_store=mock_store,
        bandit=mock_bandit,
        strategy_registry=mock_registry,
    )
    
    # Instrução muito curta -> Early Cut-off
    reward, feedback = optimizer.simulation("Curta")
    assert reward == 0.05
    assert "Early Cut-Off" in feedback
    # Não deve ter chamado o avaliador LLM
    mock_eval.assert_not_called()

def test_transposition_table_hit_in_simulation():
    emitter = JobEventEmitter()
    config = load_mcts_config()
    mock_eval = MagicMock()
    mock_store = MagicMock()
    mock_store.get_strategy_stats.return_value = {}
    mock_bandit = MagicMock()
    mock_registry = MagicMock()
    
    optimizer = Optimizer(
        skill_original="Skill original detalhada para testes de integração.",
        config=config,
        emitter=emitter,
        strategy_discoverer=MagicMock(),
        agent=MagicMock(),
        agent_cognitivo=MagicMock(),
        avaliador_modo_b=mock_eval,
        experience_store=mock_store,
        bandit=mock_bandit,
        strategy_registry=mock_registry,
    )
    
    inst = "Instrução longa e detalhada com regras claras de comportamento para o agente de IA."
    
    # Criar e registrar um nó na Tabela de Transposição
    existing_node = MCTSNode(instruction=inst)
    existing_node.q_value = 8.0
    existing_node.visits = 10
    existing_node.feedback = "Excelente instrução"
    
    from src.experience_store import hash_instruction
    key = hash_instruction(inst)
    optimizer.transposition_table.put(key, existing_node)
    
    reward, feedback = optimizer.simulation(inst)
    assert reward == 0.8
    assert feedback == "Excelente instrução"
    assert optimizer.transposition_table.hits == 1
    mock_eval.assert_not_called()

def test_transposition_table_dag_merge():
    tt = TranspositionTable()
    node1 = MCTSNode(instruction="instrução idêntica de caminho A")
    node1.q_value = 4.0
    node1.visits = 5
    
    tt.put("key_dag", node1)
    
    node2 = MCTSNode(instruction="instrução idêntica de caminho B")
    node2.q_value = 2.0
    node2.visits = 3
    
    canonical = tt.put("key_dag", node2)
    assert canonical == node1
    assert canonical.visits == 8
    assert canonical.q_value == 6.0

def test_dynamic_action_reduction():
    emitter = JobEventEmitter()
    config = load_mcts_config()
    mock_store = MagicMock()
    mock_store.get_strategy_stats.return_value = {}
    
    optimizer = Optimizer(
        skill_original="Skill original detalhada com instrução de comportamento do agente de IA.",
        config=config,
        emitter=emitter,
        strategy_discoverer=MagicMock(),
        agent=MagicMock(),
        agent_cognitivo=MagicMock(),
        avaliador_modo_b=MagicMock(),
        experience_store=mock_store,
        bandit=MagicMock(),
        strategy_registry=MagicMock(),
    )
    
    # Instrução com baixa densidade informacional (muita repetição vazia)
    repetitiva = "palavra " * 200
    assert optimizer._should_prune(repetitiva) is True

