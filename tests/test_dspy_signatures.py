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
