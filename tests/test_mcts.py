from src.domain.mcts import MCTSNode

def test_mcts_node_initialization():
    node = MCTSNode(instruction="Test instruction")
    assert node.instruction == "Test instruction"
    assert node.q_value == 0.0
    assert node.visits == 0
    assert node.feedback == ""
    assert node.children == []
    assert node.parent is None
    assert node.node_id is not None
    assert node.critica == ""
    assert node.mutation_strategy == ""
    assert node.depth == 0
    assert node.last_reward == 0.0

def test_mcts_node_max_children_allowed():
    node = MCTSNode(instruction="Test")

    # 0 visits should allow 1 child
    assert node.max_children_allowed(progressive_c=2.0, alpha=0.5) == 1

    node.visits = 1
    # ceil(2.0 * 1^0.5) = 2
    assert node.max_children_allowed(progressive_c=2.0, alpha=0.5) == 2

    node.visits = 4
    # ceil(2.0 * 4^0.5) = 4
    assert node.max_children_allowed(progressive_c=2.0, alpha=0.5) == 4

def test_mcts_node_best_child_ucb_empty():
    node = MCTSNode(instruction="Test")
    assert node.best_child_ucb(c_param=1.41) is None

def test_mcts_node_best_child_ucb_unvisited():
    parent = MCTSNode(instruction="Parent")
    child1 = MCTSNode(instruction="Child 1", parent=parent)
    child2 = MCTSNode(instruction="Child 2", parent=parent)
    parent.children = [child1, child2]

    parent.visits = 2
    # Both have 0 visits, UCB should be inf. The first one encountered might be returned
    best = parent.best_child_ucb(c_param=1.41)
    assert best in [child1, child2]

def test_mcts_node_best_child_ucb_visited():
    parent = MCTSNode(instruction="Parent")
    child1 = MCTSNode(instruction="Child 1", parent=parent)
    child2 = MCTSNode(instruction="Child 2", parent=parent)
    parent.children = [child1, child2]

    parent.visits = 10

    child1.visits = 5
    child1.q_value = 4.0  # Mean Q = 0.8

    child2.visits = 5
    child2.q_value = 3.0  # Mean Q = 0.6

    # child1 has higher Q/N (0.8 vs 0.6), same visits, so child1 should have higher UCB
    best = parent.best_child_ucb(c_param=1.41)
    assert best == child1
