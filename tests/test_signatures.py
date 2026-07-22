import pytest
from pydantic import ValidationError
from src.signatures import (
    RaciocinioCognitivo,
    MutadorCognitivoOutput,
    _validate_raciocinio,
    Avaliacao,
    AvaliacaoModoB,
    SCORE_WEIGHTS,
    calcular_composite,
    calcular_delta_reward,
    funcao_de_recompensa,
)


def test_raciocinio_cognitivo_happy_path():
    rc = RaciocinioCognitivo(
        premissas="The feedback reveals critical gaps in structure.",
        deducoes="The instruction must change its overall approach.",
        conclusao="Rewrite with structured logic and clear sections.",
    )
    assert rc.premissas
    assert rc.deducoes
    assert rc.conclusao


def test_raciocinio_cognitivo_empty_field():
    with pytest.raises((ValueError, ValidationError)):
        RaciocinioCognitivo(
            premissas="",
            deducoes="The instruction must change its approach.",
            conclusao="Rewrite with structured logic.",
        )


def test_raciocinio_cognitivo_short_field():
    with pytest.raises((ValueError, ValidationError)):
        RaciocinioCognitivo(
            premissas="short",
            deducoes="The instruction must change its approach.",
            conclusao="Rewrite with structured logic.",
        )


def test_mutador_cognitivo_output_valid():
    nova_instrucao = (
        "## Raciocínio\nThe analysis shows we need better structure here.\n"
        "## Regras\nFollow strict logical derivation in every section.\n"
        "## Conclusão\nRewrite the skill with mandatory structured output."
    )
    out = MutadorCognitivoOutput(nova_instrucao=nova_instrucao)
    assert out.nova_instrucao


def test_mutador_cognitivo_output_missing_heading_auto_fixed():
    """Auto-reparo injeta ## Conclusão ausente usando o último parágrafo."""
    out = MutadorCognitivoOutput(
        nova_instrucao=(
            "## Raciocínio\nThe analysis shows we need better structure here.\n"
            "## Regras\nFollow strict logical derivation in every section.\n"
            "Missing the conclusao heading entirely here."
        )
    )
    assert out.auto_fix is True
    assert '## Conclusão' in out.nova_instrucao or '## Conclusao' in out.nova_instrucao


def test_mutador_cognitivo_output_still_fails_when_unrepairable():
    """Se o texto for curto demais, auto-reparo não consegue injetar seções e ainda levanta erro."""
    with pytest.raises((ValueError, ValidationError)):
        MutadorCognitivoOutput(
            nova_instrucao="Just a short text without any headings."
        )


def test_mutador_cognitivo_output_auto_fix_injects_raciocinio():
    """Quando falta ## Raciocínio mas ## Regras existe, o prefixo vira ## Raciocínio."""
    out = MutadorCognitivoOutput(
        nova_instrucao=(
            "This is the reasoning part that should become raciocinio.\n"
            "It has enough content to qualify for auto-fix injection.\n"
            "## Regras\nFollow strict logical derivation.\n"
            "## Conclusao\nFinal conclusion here."
        )
    )
    assert out.auto_fix is True
    assert '## Raciocínio' in out.nova_instrucao or '## Raciocinio' in out.nova_instrucao


def test_mutador_cognitivo_output_valid_no_fix_needed():
    """Quando todas as seções estão presentes, auto_fix é False."""
    out = MutadorCognitivoOutput(
        nova_instrucao=(
            "## Raciocinio\nReasoning here.\n"
            "## Regras\nRules here.\n"
            "## Conclusao\nConclusion here."
        )
    )
    assert out.auto_fix is False


def test_mutador_cognitivo_output_accent_insensitive():
    """Headings com ou sem acentos, maiúsculas/minúsculas são todos aceitos."""
    out = MutadorCognitivoOutput(
        nova_instrucao=(
            "## RACIOCÍNIO\nReasoning.\n"
            "## regras\nRules.\n"
            "## ConCluSãO\nConclusion."
        )
    )
    assert out.auto_fix is False


def test_validate_raciocinio_valid():
    raw = (
        "Premissas: the feedback reveals critical gaps in the current approach.\n"
        "Deducoes: the instruction must change to address structural issues.\n"
        "Conclusao: rewrite with structured logic and mandatory sections."
    )
    _validate_raciocinio(raw)


def test_validate_raciocinio_missing_label():
    raw = (
        "Premissas: the feedback reveals critical gaps in the current approach.\n"
        "Conclusao: rewrite with structured logic and mandatory sections."
    )
    with pytest.raises((ValueError, ValidationError)):
        _validate_raciocinio(raw)


def test_mutador_cognitivo_agent_output_fields():
    from src.infrastructure.dspy_impl import MutadorCognitivoAgentSignature
    output_fields = MutadorCognitivoAgentSignature.output_fields
    assert "raciocinio_estruturado" in output_fields
    assert "critica" in output_fields
    assert "nova_instrucao" in output_fields


def test_mutador_cognitivo_agent_input_fields():
    from src.infrastructure.dspy_impl import MutadorCognitivoAgentSignature
    input_fields = MutadorCognitivoAgentSignature.input_fields
    assert "instrucao_anterior" in input_fields
    assert "nota_anterior" in input_fields
    assert "feedback_juiz" in input_fields
    assert "estrategia_mutacao" in input_fields


# ---------------------------------------------------------------------------
# Reward function + composite scoring — previously under-covered.
# Contratos sob teste (src/signatures.py):
#   - SCORE_WEIGHTS: tabela única de pesos (robustez+acionabilidade valem +)
#   - calcular_composite: clamp [0,100] por dimensão, média ponderada em [0,1]
#   - calcular_delta_reward: alpha*abs + (1-alpha)*max(0,delta), clamp [0,1]
#   - funcao_de_recompensa: critical-rules gate, penalty por defeito,
#     fail-closed (0.0) em exceção
# ---------------------------------------------------------------------------


def _avaliacao_modo_b(*, crit=True, defects=None, note=80.0, feedback="fb"):
    """Fábrica de AvaliacaoModoB com notas uniformes p/ asserts determinísticos."""
    return AvaliacaoModoB(
        manteve_regras_criticas=crit,
        nota_clareza=note,
        nota_formatacao=note,
        nota_robustez=note,
        nota_densidade_informacional=note,
        nota_acionabilidade=note,
        nota_anti_fragilidade=note,
        feedback_detalhado=feedback,
        defeitos_encontrados=defects if defects is not None else [],
    )


class _NotaHolder:
    """Objeto simples expondo apenas os atributos nota_* p/ calcular_composite."""
    def __init__(self, value):
        for f, _ in SCORE_WEIGHTS:
            setattr(self, f, value)


# --- calcular_composite -----------------------------------------------------


def test_score_weights_total_and_relative_robustness():
    # Robustez e acionabilidade são as dimensões mais pesadas (mais críticas).
    # Ajuste manual provisorio (Fase 4 — DESIGN.md §7.7):
    #   densidade_informacional 1.0→1.4, acionabilidade 1.3→1.4
    weights = dict(SCORE_WEIGHTS)
    assert weights['nota_robustez'] == 1.2
    assert weights['nota_acionabilidade'] == 1.4
    assert weights['nota_densidade_informacional'] == 1.4
    # Total: 1.0 + 0.8 + 1.2 + 1.4 + 1.4 + 1.2 = 7.0
    assert sum(w for _, w in SCORE_WEIGHTS) == pytest.approx(7.0)


def test_calcular_composite_all_max_is_one():
    assert calcular_composite(_NotaHolder(100.0)) == pytest.approx(1.0)


def test_calcular_composite_all_zero_is_zero():
    assert calcular_composite(_NotaHolder(0.0)) == pytest.approx(0.0)


def test_calcular_composite_clamps_above_hundred():
    # Notas >100 são clampadas a 100 — nunca extrapolam o teto.
    assert calcular_composite(_NotaHolder(150.0)) == pytest.approx(1.0)


def test_calcular_composite_clamps_below_zero():
    # Notas negativas são clampadas a 0.
    assert calcular_composite(_NotaHolder(-25.0)) == pytest.approx(0.0)


def test_calcular_composite_uniform_note_equals_note_over_hundred():
    # Notas uniformes: composite = nota/100 (independente dos pesos).
    assert calcular_composite(_NotaHolder(80.0)) == pytest.approx(0.8)
    assert calcular_composite(_NotaHolder(40.0)) == pytest.approx(0.4)


def test_calcular_composite_weights_higher_dimension_more():
    # Mesma média aritmética, mas concentrada na dimensão mais pesada
    # (acionabilidade) → composite maior. Prova que os pesos agem.
    heavy = _NotaHolder(0.0)
    setattr(heavy, 'nota_acionabilidade', 100.0)  # peso 1.3
    light = _NotaHolder(0.0)
    setattr(light, 'nota_clareza', 100.0)  # peso 1.0
    assert calcular_composite(heavy) > calcular_composite(light)


def test_calcular_composite_missing_attribute_defaults_to_zero():
    # getattr(notas, field, 0.0) — atributo ausente vira 0, não AttributeError.
    class Partial:
        nota_clareza = 100.0
    # Demais dimensões ausentes → tratadas como 0.
    score = calcular_composite(Partial())
    assert 0.0 < score < 1.0


# --- calcular_delta_reward --------------------------------------------------


def test_delta_reward_improvement_adds_bonus():
    # filho>pai: delta>0 entra no shaping.
    # 0.6*0.8 + 0.4*0.3 = 0.48 + 0.12 = 0.60
    assert calcular_delta_reward(0.8, 0.5) == pytest.approx(0.60)


def test_delta_reward_regression_floors_delta_to_zero():
    # filho<pai: delta=-0.3 → shaped = 0.6*0.5 + 0.4*(-0.3) = 0.30 - 0.12 = 0.18
    # O delta negativo penaliza, sinalizando ao bandit que houve regressão.
    assert calcular_delta_reward(0.5, 0.8) == pytest.approx(0.18)


def test_delta_reward_equal_rewards_is_alpha_times_absolute():
    # delta=0 → shaped = alpha*reward.
    assert calcular_delta_reward(0.9, 0.9, alpha=0.6) == pytest.approx(0.54)


def test_delta_reward_clamps_to_unit_interval():
    # Filho=1, pai=0 → 0.6*1 + 0.4*1 = 1.0 (teto). Não extrapola.
    assert calcular_delta_reward(1.0, 0.0) == pytest.approx(1.0)


def test_delta_reward_custom_alpha_changes_balance():
    # alpha=1.0 → peso total no absoluto, delta ignorado.
    assert calcular_delta_reward(0.8, 0.5, alpha=1.0) == pytest.approx(0.8)
    # alpha=0.0 → peso total no delta (limitado a melhorias).
    assert calcular_delta_reward(0.8, 0.5, alpha=0.0) == pytest.approx(0.3)


# --- funcao_de_recompensa ---------------------------------------------------


def test_funcao_recompensa_happy_path_no_defects():
    av = _avaliacao_modo_b(note=80.0)
    score, feedback = funcao_de_recompensa(lambda **kw: av, "orig", "opt", "regras")
    assert score == pytest.approx(0.8)
    assert feedback == "fb"


def test_funcao_recompensa_critical_rules_violated_returns_zero():
    # Hard-gate: quebra de regra crítica zera a recompensa, preservando feedback.
    av = _avaliacao_modo_b(crit=False, note=95.0)
    score, feedback = funcao_de_recompensa(lambda **kw: av, "orig", "opt", "regras")
    assert score == 0.0
    assert feedback == "fb"


def test_funcao_recompensa_defects_apply_linear_penalty():
    # 3 defeitos → -0.3 sobre o composite base 0.8.
    av = _avaliacao_modo_b(note=80.0, defects=['d1', 'd2', 'd3'])
    score, feedback = funcao_de_recompensa(lambda **kw: av, "orig", "opt", "regras")
    assert score == pytest.approx(0.5)
    # Feedback trocado pelo bullet-list de defeitos.
    assert feedback.startswith("DEFEITOS")
    for d in ('d1', 'd2', 'd3'):
        assert d in feedback


def test_funcao_recompensa_defect_penalty_floors_at_zero():
    # Muitos defeitos + nota baixa → clamp em 0, nunca negativo.
    av = _avaliacao_modo_b(note=10.0, defects=['d'] * 20)  # penalty -2.0
    score, _ = funcao_de_recompensa(lambda **kw: av, "orig", "opt", "regras")
    assert score == 0.0


def test_funcao_recompensa_empty_defects_list_is_happy_path():
    # defeitos_encontrados=[] é falsy → não aciona penalty.
    av = _avaliacao_modo_b(note=80.0, defects=[])
    score, feedback = funcao_de_recompensa(lambda **kw: av, "orig", "opt", "regras")
    assert score == pytest.approx(0.8)
    assert feedback == "fb"


def test_funcao_recompensa_exception_returns_zero_and_error_message():
    # Fail-closed: qualquer exceção do juiz → (0.0, mensagem de erro).
    def exploding_judge(**kw):
        raise RuntimeError("DSPy offline")
    score, feedback = funcao_de_recompensa(exploding_judge, "orig", "opt", "regras")
    assert score == 0.0
    assert "Erro interno" in feedback
    assert "DSPy offline" in feedback


def test_funcao_recompensa_forwards_all_arguments_to_judge():
    # Contrato: o juiz recebe exatamente skill_original/skill_otimizada/regras.
    received = {}
    def capturing_judge(**kw):
        received.update(kw)
        return _avaliacao_modo_b()
    funcao_de_recompensa(capturing_judge, "ORIG", "OPT", "REGRAS")
    assert received == {"skill_original": "ORIG",
                        "skill_otimizada": "OPT",
                        "regras_adicionais": "REGRAS"}


# --- Avaliacao note validation (judge output contract) ---------------------


def _av_kwargs(**overrides):
    """Defaults válidos p/ Avaliacao; sobrescreve apenas o campo sob teste."""
    base = dict(
        manteve_regras_criticas=True,
        nota_clareza=80, nota_formatacao=80, nota_robustez=80,
        nota_densidade_informacional=80, nota_acionabilidade=80,
        nota_anti_fragilidade=80, feedback_detalhado="f",
    )
    base.update(overrides)
    return base


def test_avaliacao_coerces_integer_note_to_float():
    av = Avaliacao(**_av_kwargs(nota_clareza=80))
    assert av.nota_clareza == 80.0
    assert isinstance(av.nota_clareza, float)



def test_avaliacao_rejects_note_above_hundred():
    with pytest.raises(ValueError, match="entre 0 e 100"):
        Avaliacao(**_av_kwargs(nota_clareza=150))


def test_avaliacao_rejects_negative_note():
    with pytest.raises(ValueError, match="entre 0 e 100"):
        Avaliacao(**_av_kwargs(nota_clareza=-1))


def test_avaliacao_validates_all_six_dimensions():
    # Cada uma das 6 dimensões é validada independentemente.
    dims = ['nota_clareza', 'nota_formatacao', 'nota_robustez',
            'nota_densidade_informacional', 'nota_acionabilidade',
            'nota_anti_fragilidade']
    for d in dims:
        with pytest.raises(ValueError):
            Avaliacao(**_av_kwargs(**{d: 999}))
