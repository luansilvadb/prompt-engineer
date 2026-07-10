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
    text = ("a casa e bela. o gato e mau. o cao e bom. a flor e linda. o sol e quente. "
            "o ceu e azul. o mar e salgado. a lua e cheia. o dia e claro. a noite e fria. "
            "o riso e alto. o som e baixo. o vento e forte. o fogo e quente. a agua e fria. "
            "a terra e seca. o rio e largo. a rua e curta. a ponte e nova. o muro e alto. "
            "a porta e aberta. o quarto e limpo. a cama e boa. a mesa e larga. a sala e vazia. "
            "o banco e duro. o preco e justo. o peso e leve. a cor e viva. o brilho e forte. "
            "a voz e calma. o olhar e firme. o toque e leve. o som e doce. a paz e rara. "
            "o bem e certo. o mal e errado. a mao e sua. a fe e boa. a lei e justa. "
            "o dom e seu. o par e bom. o fim e perto. a luz e clara. a via e longa. "
            "a vez e unica. o sim e seu. o nao e claro. o talvez e seu. o tudo e nada. "
            "o nada e tudo. o mais e seu.")
    result = evaluate_heuristics(text)
    assert result["prune"] is False
    assert result["penalty_multiplier"] < 1.0
