import dspy
from src.infrastructure.dspy_impl import AvaliadorModoBSignature, StrategyDiscovererSignature, SelfReflectiveAgentSignature

def test_dspy_signatures_structure():
    # Verifica que as assinaturas do DSPy herdam de dspy.Signature e possuem os campos esperados
    assert issubclass(AvaliadorModoBSignature, dspy.Signature)
    assert issubclass(StrategyDiscovererSignature, dspy.Signature)
    assert issubclass(SelfReflectiveAgentSignature, dspy.Signature)
    
    # AvaliadorModoBSignature
    fields = AvaliadorModoBSignature.fields
    assert 'skill_original' in fields
    assert 'skill_otimizada' in fields
    assert 'regras_adicionais' in fields
    assert 'manteve_regras_criticas' in fields
    assert 'nota_clareza' in fields

def test_dspy_predict_instantiation():
    # Verifica instanciação do dspy.Predict com a signature
    predict_module = dspy.Predict(AvaliadorModoBSignature)
    assert predict_module.signature == AvaliadorModoBSignature


def test_normalize_json_keys_converts_hyphen_to_underscore():
    """_normalize_json_keys deve converter hífen para underscore em chaves JSON."""
    from src.infrastructure.dspy_impl import _normalize_json_keys

    input_text = '{"nota_anti-fragilidade": 98, "feedback_detalhado": "ok"}'
    expected = '{"nota_anti_fragilidade": 98, "feedback_detalhado": "ok"}'
    result = _normalize_json_keys(input_text)
    assert result == expected


def test_normalize_json_keys_no_op_for_underscore():
    """_normalize_json_keys deve ser no-op quando chaves já usam underscore."""
    from src.infrastructure.dspy_impl import _normalize_json_keys

    input_text = '{"nota_anti_fragilidade": 98, "nota_clareza": 95}'
    result = _normalize_json_keys(input_text)
    assert result == input_text  # inalterado


def test_normalize_json_keys_multiple_hyphens():
    """_normalize_json_keys deve normalizar múltiplas chaves com hífen simultaneamente."""
    from src.infrastructure.dspy_impl import _normalize_json_keys

    input_text = (
        '{"nota-clareza": 95, "nota-formatacao": 90, '
        '"nota-robustez": 88, "nota-densidade-informacional": 85, '
        '"nota-acionabilidade": 92, "nota-anti-fragilidade": 98}'
    )
    expected = (
        '{"nota_clareza": 95, "nota_formatacao": 90, '
        '"nota_robustez": 88, "nota_densidade_informacional": 85, '
        '"nota_acionabilidade": 92, "nota_anti_fragilidade": 98}'
    )
    result = _normalize_json_keys(input_text)
    assert result == expected


def test_normalize_json_keys_preserves_values_and_structure():
    """_normalize_json_keys deve preservar valores, estrutura e campos sem hífen."""
    from src.infrastructure.dspy_impl import _normalize_json_keys

    input_text = (
        '{\n'
        '  "nota_anti-fragilidade": 98,\n'
        '  "nota-clareza": 95,\n'
        '  "manteve_regras_criticas": true,\n'
        '  "feedback_detalhado": "ótimo trabalho"\n'
        '}'
    )
    result = _normalize_json_keys(input_text)

    assert '"nota_anti_fragilidade": 98' in result  # underscore → preservado
    assert '"nota_clareza": 95' in result  # hyphen → convertido
    assert '"manteve_regras_criticas": true' in result  # underscore → preservado
    assert '"feedback_detalhado": "ótimo trabalho"' in result  # sem hífen → preservado
    assert 'nota-anti-fragilidade' not in result  # hífen removido
    assert 'nota-clareza' not in result  # hífen removido


def test_outputfield_descriptors_contain_anti_hyphen_instruction():
    """Todos os OutputField de nota nas Signatures devem conter instrução anti-hífen."""
    from src.infrastructure.dspy_impl import AvaliadorDeSkillSignature, AvaliadorModoBSignature

    anti_hyphen_instruction = "use underscore '_' not hyphen '-' in field names"

    nota_fields = [
        'nota_clareza', 'nota_formatacao', 'nota_robustez',
        'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade',
    ]

    for field_name in nota_fields:
        for sig in [AvaliadorDeSkillSignature, AvaliadorModoBSignature]:
            field = sig.fields[field_name]
            desc = field.json_schema_extra.get('desc', '') if hasattr(field, 'json_schema_extra') else ''
            assert anti_hyphen_instruction in desc, (
                f"Field {field_name} in {sig.__name__} missing anti-hyphen instruction. "
                f"desc='{desc}'"
            )
