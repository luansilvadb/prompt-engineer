from unittest.mock import MagicMock, patch

from src.domain.mcts import MCTSNode
from src.drift.runner import _apply_verification_hints
from src.signatures import AvaliacaoModoB, funcao_de_recompensa


# =============================================================
# BUG-1: Fallback retorna pai em vez de criar filho identico
# =============================================================
def test_bug1_fallback_returns_leaf_not_useless_child(mock_optimizer_factory):
    """
    BUG-1 CORRIGIDO [optimizer.py L345]: o fallback anterior criava um filho
    com `leaf.instruction + '\\n '`, identico ao pai apos strip(), desperdicando
    1 avaliacao LLM. Apos a correcao, _expand_node retorna o proprio no pai
    quando todas as 3 tentativas de mutacao falham.

    Contrato do fix: `returned_node is parent` (sem filho inutil criado).
    """
    opt = mock_optimizer_factory(skill_original="Instrucao original de teste.")
    opt.agent = MagicMock(side_effect=Exception("LLM indisponivel"))
    opt.agent_cognitivo = MagicMock(side_effect=Exception("LLM indisponivel"))
    opt.mutation_bandit.select = MagicMock(return_value="default")
    opt._strategy_registry.get_prompt = MagicMock(return_value="Prompt")
    opt._strategy_registry.get_name = MagicMock(return_value="default")

    parent = MCTSNode(instruction="Instrucao original de teste.", depth=0)
    filhos_antes = len(parent.children)
    result = opt._expand_node(parent)

    # Novo contrato: retorna o proprio pai sem criar filho inutil
    assert result is parent, (
        "BUG-1 fix: _expand_node deve retornar o no pai quando todas as tentativas "
        "falham. Obtido: %s" % repr(result)
    )
    assert len(parent.children) == filhos_antes, (
        "BUG-1 fix: nenhum filho deve ser criado no fallback. "
        "Filhos antes=%d, depois=%d" % (filhos_antes, len(parent.children))
    )


# =============================================================
# BUG-2 CORRIGIDO: Token count cumulativo entre iteracoes
# =============================================================
def test_bug2_llm_call_count_cumulative_across_iterations(mock_optimizer_factory):
    """BUG-2 CORRIGIDO: _total_llm_calls acumula entre iteracoes."""
    opt = mock_optimizer_factory(skill_original="Skill teste")

    opt._count_llm_call(3)
    opt._emit_cost_event(iteration=0)

    opt._count_llm_call(2)
    opt._emit_cost_event(iteration=1)

    assert hasattr(opt, "_total_llm_calls"), \
        "Optimizer sem atributo _total_llm_calls cumulativo."
    assert opt._total_llm_calls == 5, \
        "Total cumulativo esperado=5, obtido=%d" % opt._total_llm_calls


# =============================================================
# BUG-3 CORRIGIDO: best_node nunca retorna raiz quando ha filhos
# =============================================================
def test_bug3_best_node_never_returns_root_when_child_exists(mock_optimizer_factory):
    """BUG-3 CORRIGIDO: raiz filtrada de _select_and_log_best_node."""
    opt = mock_optimizer_factory(skill_original="Skill original")
    opt._emitter.is_cancelled = MagicMock(return_value=False)

    root = MCTSNode(instruction="Skill original", depth=0)
    root.q_value = 0.9
    root.visits = 1

    child = MCTSNode(instruction="Skill otimizada", parent=root, depth=1)
    child.q_value = 0.5
    child.visits = 1
    root.children.append(child)

    best = opt._select_and_log_best_node(root)

    assert best != root, (
        "Raiz nao deve ser retornada quando existe filho."
    )
    assert best == child


# =============================================================
# BUG-4 CORRIGIDO: Penalidade de defeitos com teto em 0.5
# =============================================================
def test_bug4_defect_penalty_has_ceiling():
    """BUG-4 CORRIGIDO: penalty = min(N*0.1, 0.5). 6 defeitos leves -> score >= 0.30."""
    mock_avaliador = MagicMock()
    mock_avaliador.return_value = AvaliacaoModoB(
        manteve_regras_criticas=True,
        nota_clareza=80.0,
        nota_formatacao=80.0,
        nota_robustez=80.0,
        nota_densidade_informacional=80.0,
        nota_acionabilidade=80.0,
        nota_anti_fragilidade=80.0,
        feedback_detalhado="Feedback.",
        defeitos_encontrados=["Defeito leve #%d" % i for i in range(6)],
    )

    score, _ = funcao_de_recompensa(
        skill_original="original",
        skill_otimizada="otimizada",
        regras_adicionais="",
        avaliador_modo_b=mock_avaliador,
    )

    assert score >= 0.30, (
        "score=%.3f com 6 defeitos leves. Com teto 0.5, minimo esperado=0.30." % score
    )


# =============================================================
# BUG-5: Safety-net SD-2 ? diagnostico de dados
# =============================================================
def test_bug5_safety_net_silent_when_hints_empty():
    """CONTRACT: hints vazio -> None. Documenta por que SD-2 nao dispara."""
    result = _apply_verification_hints(
        skill_otimizada="Esta skill viola a regra proibida.",
        regras_adicionais="NAO use a palavra proibida.",
        hints=[],
    )
    assert result is None


def test_bug5_safety_net_fires_when_hint_matches():
    """CONTRACT: hint presente -> True."""
    result = _apply_verification_hints(
        skill_otimizada="Esta skill usa a palavra proibida.",
        regras_adicionais="Regra: nao use palavras proibidas.",
        hints=["palavra proibida"],
    )
    assert result is True


def test_bug5_safety_net_returns_none_when_no_match():
    """CONTRACT: hint nao bate -> None."""
    result = _apply_verification_hints(
        skill_otimizada="Esta skill esta limpa e bem escrita.",
        regras_adicionais="Regra: nao use palavras proibidas.",
        hints=["palavra proibida"],
    )
    assert result is None


# =============================================================
# BUG-6 CORRIGIDO: logger em vez de print() em golden.py
# =============================================================
def test_bug6_golden_contamination_uses_logger_not_print():
    """BUG-6 CORRIGIDO: _validate_circular_contamination usa logger.warning(), nao print()."""
    from src.drift.models import ProbeExpectation, GoldenProbe
    from src.drift.golden import GoldenSet

    probe = GoldenProbe(
        id="SD-test",
        skill_original="original",
        skill_otimizada="otimizada",
        regras_adicionais="",
        expected=ProbeExpectation(
            manteve_regras_criticas=True,
            nota_clareza=80.0, nota_formatacao=80.0,
            nota_robustez=80.0, nota_densidade_informacional=80.0,
            nota_acionabilidade=80.0, nota_anti_fragilidade=80.0,
        ),
        expected_rank_band="alto",
        verifier="human",
        category="general",
        generator_model="gpt-4o",
        verification_hints=[],
    )

    gs = GoldenSet.__new__(GoldenSet)
    gs.probes = [probe]
    gs.version = "test"
    gs.curated_at = "2026-01-01"

    with patch("builtins.print") as mock_print, \
         patch.dict("os.environ", {"MODEL_NAME": "gpt-4o"}):
        gs._validate_circular_contamination()
        assert not mock_print.called, (
            "BUG-6: print() chamado %dx. Deve usar logger.warning()." % mock_print.call_count
        )


# =============================================================
# CONTRACTS ? comportamento correto atual (devem SEMPRE passar)
# =============================================================

def test_contract_one_defect_penalty_is_010():
    """1 defeito -> penalty=0.1. Deve passar antes e apos a correcao do BUG-4."""
    mock_avaliador = MagicMock()
    mock_avaliador.return_value = AvaliacaoModoB(
        manteve_regras_criticas=True,
        nota_clareza=80.0, nota_formatacao=80.0,
        nota_robustez=80.0, nota_densidade_informacional=80.0,
        nota_acionabilidade=80.0, nota_anti_fragilidade=80.0,
        feedback_detalhado="Feedback.",
        defeitos_encontrados=["Um unico defeito cosm?tico"],
    )
    score, _ = funcao_de_recompensa(
        skill_original="original",
        skill_otimizada="otimizada",
        regras_adicionais="",
        avaliador_modo_b=mock_avaliador,
    )
    assert 0.65 <= score <= 0.75, (
        "1 defeito deve gerar score ~0.70. Obtido=%.3f" % score
    )


def test_contract_critical_rule_violation_returns_zero():
    """Violacao critica -> score=0.0 independente de outras notas."""
    mock_avaliador = MagicMock()
    mock_avaliador.return_value = AvaliacaoModoB(
        manteve_regras_criticas=False,
        nota_clareza=90.0, nota_formatacao=90.0,
        nota_robustez=90.0, nota_densidade_informacional=90.0,
        nota_acionabilidade=90.0, nota_anti_fragilidade=90.0,
        feedback_detalhado="Viola regra critica.",
        defeitos_encontrados=[],
    )
    score, _ = funcao_de_recompensa(
        skill_original="original",
        skill_otimizada="otimizada",
        regras_adicionais="Regra obrigatoria.",
        avaliador_modo_b=mock_avaliador,
    )
    assert score == 0.0
