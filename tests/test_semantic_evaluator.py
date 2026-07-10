import pytest
from src.semantic_evaluator import calculate_semantic_penalty, get_embedder

def test_singleton_loading():
    embedder1 = get_embedder()
    embedder2 = get_embedder()
    assert embedder1 is embedder2

def test_no_penalty():
    text1 = "A completely different concept for testing."
    text2 = "Another unrelated string that has no semantic similarity whatsoever."
    penalty = calculate_semantic_penalty(text1, text2)
    assert penalty == 1.0

def test_continuous_decay():
    # Should trigger decay between 0.01 and 1.0
    text1 = "Resolva esta equação de segundo grau."
    text2 = "Resolva esta equação do segundo grau."
    penalty = calculate_semantic_penalty(text1, text2)
    assert 0.01 <= penalty < 1.0

def test_max_penalty():
    text = "This is a strictly identical text used for testing."
    penalty = calculate_semantic_penalty(text, text)
    assert penalty == 0.01
