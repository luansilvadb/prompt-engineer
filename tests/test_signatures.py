import pytest
from pydantic import ValidationError
from src.signatures import (
    RaciocinioCognitivo,
    MutadorCognitivoOutput,
    _validate_raciocinio,
)
from src.infrastructure.dspy_impl import DSPyMutadorCognitivoAgent as MutadorCognitivoAgent


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
    with pytest.raises(ValidationError):
        RaciocinioCognitivo(
            premissas="",
            deducoes="The instruction must change its approach.",
            conclusao="Rewrite with structured logic.",
        )


def test_raciocinio_cognitivo_short_field():
    with pytest.raises(ValidationError):
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


def test_mutador_cognitivo_output_missing_heading():
    with pytest.raises(ValidationError):
        MutadorCognitivoOutput(
            nova_instrucao=(
                "## Raciocínio\nThe analysis shows we need better structure here.\n"
                "## Regras\nFollow strict logical derivation in every section.\n"
                "Missing the conclusao heading entirely here."
            )
        )


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
    output_fields = MutadorCognitivoAgent.output_fields
    assert "raciocinio_estruturado" in output_fields
    assert "critica" in output_fields
    assert "nova_instrucao" in output_fields


def test_mutador_cognitivo_agent_input_fields():
    input_fields = MutadorCognitivoAgent.input_fields
    assert "instrucao_anterior" in input_fields
    assert "nota_anterior" in input_fields
    assert "feedback_juiz" in input_fields
    assert "estrategia_mutacao" in input_fields
