import pytest
from src.domain.mcts import MCTSNode, TranspositionTable

def test_mcts_node_merge_stats():
    node_a = MCTSNode("instrucao_teste")
    node_b = MCTSNode("instrucao_teste")
    
    node_a.visits = 2
    node_a.q_value = 1.6
    node_a.sq_q_value = 1.3
    node_a.last_reward = 0.8
    
    node_b.visits = 3
    node_b.q_value = 2.4
    node_b.sq_q_value = 1.9
    node_b.last_reward = 0.9

    node_a.merge_stats(node_b)
    
    assert node_a.visits == 5
    assert pytest.approx(node_a.q_value, 0.01) == 4.0
    assert pytest.approx(node_a.sq_q_value, 0.01) == 3.2
    assert node_a.last_reward == 0.9

def test_transposition_table_dag_put_merges_stats():
    tt = TranspositionTable()
    
    node_a = MCTSNode("Instrução Exemplo\n## Regras\n1. Regra A")
    node_a.visits = 4
    node_a.q_value = 3.2
    
    canonical = tt.put("Instrução Exemplo\n## Regras\n1. Regra A", node_a)
    assert canonical is node_a
    
    node_b = MCTSNode("Instrução Exemplo\n## Regras\n1. Regra A")
    node_b.visits = 2
    node_b.q_value = 1.8
    
    merged_canonical = tt.put("Instrução Exemplo\n## Regras\n1. Regra A", node_b)
    assert merged_canonical is node_a
    assert node_a.visits == 6
    assert pytest.approx(node_a.q_value, 0.01) == 5.0

def test_transposition_table_get_hits():
    tt = TranspositionTable()
    node = MCTSNode("Instrução de teste")
    tt.put("Instrução de teste", node)
    
    retrieved = tt.get("Instrução de teste")
    assert retrieved is node
    assert tt.hits == 1
    assert tt.lookups == 1
    assert tt.hit_rate == 1.0
