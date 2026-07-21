import pytest
from src.domain.mcts import MCTSNode

def test_mcts_node_variance_and_ucb_tuned():
    parent = MCTSNode("Pai")
    child1 = MCTSNode("Filho 1", parent=parent)
    child2 = MCTSNode("Filho 2", parent=parent)
    parent.children = [child1, child2]

    # Simular recompensas constantes para child1 (variância 0)
    for r in [0.8, 0.8, 0.8, 0.8]:
        child1.q_value += r
        child1.sq_q_value += r ** 2
        child1.visits += 1
        parent.visits += 1

    # Simular recompensas ruidosas para child2 (alta variância)
    for r in [0.2, 1.0, 0.2, 1.0]:
        child2.q_value += r
        child2.sq_q_value += r ** 2
        child2.visits += 1
        parent.visits += 1

    assert child1.variance() == pytest.approx(0.0)
    assert child2.variance() > 0.1

    # Seleção UCB1-Tuned deve estar disponível
    best = parent.best_child_ucb_tuned(c_param=1.0)
    assert best in [child1, child2]

def test_quality_metric_in_teleprompter():
    pred_valido = {
        'manteve_regras_criticas': True,
        'feedback_detalhado': 'Feedback satisfatório com mais de 5 caracteres',
        'nota_qualidade': 0.85
    }
    
    pred_invalido_regras = {
        'manteve_regras_criticas': False,
        'feedback_detalhado': 'Feedback satisfatório',
    }

    pred_invalido_curto = {
        'manteve_regras_criticas': True,
        'feedback_detalhado': 'curt',
    }

    class MockPred:
        def __init__(self, manteve, feedback, nota=None):
            self.manteve_regras_criticas = manteve
            self.feedback_detalhado = feedback
            self.nota_qualidade = nota

    mock_ok = MockPred(True, "Feedback bem detalhado e explicativo", 0.9)
    mock_bad = MockPred(False, "Critica ruim", 0.1)

    def check_metric(pred):
        if not pred:
            return False
        manteve = getattr(pred, 'manteve_regras_criticas', None)
        if manteve is None and isinstance(pred, dict):
            manteve = pred.get('manteve_regras_criticas', False)
        if isinstance(manteve, str):
            manteve = manteve.lower() in ('true', '1', 'sim')
        if not manteve:
            return False

        feedback = getattr(pred, 'feedback_detalhado', '')
        if not feedback and isinstance(pred, dict):
            feedback = pred.get('feedback_detalhado', '')
        if not feedback or len(str(feedback).strip()) < 5:
            return False

        nota = getattr(pred, 'nota_qualidade', None)
        if nota is None and isinstance(pred, dict):
            nota = pred.get('nota_qualidade', None)
        if nota is not None:
            try:
                val = float(nota)
                if val < 0.0:
                    return False
            except (ValueError, TypeError):
                pass
        return True

    assert check_metric(pred_valido) is True
    assert check_metric(pred_invalido_regras) is False
    assert check_metric(pred_invalido_curto) is False
    assert check_metric(mock_ok) is True
    assert check_metric(mock_bad) is False
