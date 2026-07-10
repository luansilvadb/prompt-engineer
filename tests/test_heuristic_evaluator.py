import pytest
from src.heuristic_evaluator import evaluate_heuristics

def test_short_text_bypass():
    result = evaluate_heuristics("Curto e direto.")
    assert result["prune"] is False
    assert result["penalty_multiplier"] == 1.0

def test_low_lexical_density_prune():
    text = "palavra " * 100
    result = evaluate_heuristics(text)
    assert result["prune"] is True
    assert result["penalty_multiplier"] == 0.0

def test_layer_2_penalty():
    # Long text with high flesch reading ease (simple repetitive words)
    text = "O gato senta no tapete macio e dorme bem. " * 30
    result = evaluate_heuristics(text)
    assert result["prune"] is False
    assert result["penalty_multiplier"] < 1.0
