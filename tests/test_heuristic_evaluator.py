from src.evaluators import evaluate_heuristics

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


# ── Layer 0: Vague Buzzword Detection ────────────────────────────────────────

def test_layer0_buzzword_threshold_triggers_penalty():
    """Text with >= buzzword_threshold hits receives progressive penalty.
    
    "moreover", "furthermore", "in conclusion", "pivotal", "seamlessly",
    "robust", "paradigm", "leverage", "synergy", "landscape", "groundbreaking",
    "cutting-edge" = ~12 EN buzzwords.
    With threshold=3, excess=10 -> penalty = max(0.30, 1.0 - 1.0) = 0.30
    """
    text = (
        "Moreover, this approach is pivotal. Furthermore, it seamlessly integrates all "
        "components. In conclusion, the system is robust. The paradigm shift leverages "
        "synergy across the entire landscape. This is groundbreaking and cutting-edge work."
    )
    result = evaluate_heuristics(text)
    assert result["prune"] is False
    # Progressive penalty: ~12 hits with threshold=3 -> penalty ~0.30
    assert 0.25 <= result["penalty_multiplier"] <= 0.35, (
        f"Expected ~0.30, got {result['penalty_multiplier']}"
    )
    assert "Vague Buzzwords" in result["reason"]


def test_layer0_below_threshold_passes():
    """Text with fewer hits than buzzword_threshold should NOT trigger Layer 0 penalty.

    Exactly 2 buzzword matches (furthermore + robust) — below the injected threshold of 3.
    The text is long enough (>30 words) to pass the short-text guard.
    """
    text = (
        "Furthermore, the proposed method shows promise in real-world scenarios. "
        "The results are robust across all test environments examined in this study. "
        "Additional benchmarks will be needed to confirm the generalizability of the findings "
        "and validate the approach against established baselines in the field."
    )
    result = evaluate_heuristics(text, buzzword_threshold=3)
    # 2 hits < threshold=3 → Layer 0 must NOT trigger penalty
    assert "Vague Buzzwords" not in result.get("reason", ""), (
        f"Layer 0 triggered unexpectedly. reason={result['reason']}"
    )


def test_layer0_short_text_not_reached():
    """Short texts bypass ALL layers, including Layer 0 — word-count guard comes first."""
    short_buzzword_text = "Moreover, furthermore, in conclusion."
    result = evaluate_heuristics(short_buzzword_text)
    assert result["penalty_multiplier"] == 1.0
    assert result["reason"] == "Bypassed (short text)"


def test_layer0_pt_buzzwords_trigger_penalty():
    """Portuguese buzzwords should also be detected with progressive penalty."""
    text = (
        "Cabe ressaltar que, em suma, é importante destacar a relevância do método. "
        "No contexto atual, o sistema é de extrema importância para a comunidade. "
        "Em conclusão, o resultado foi valioso e deve ser ampliado. "
        "No cenário atual, a abordagem é fundamentalmente valiosa para todos."
    )
    result = evaluate_heuristics(text)
    assert result["prune"] is False
    # Progressive penalty for ~8-9 PT buzzwords: excess ~6-7 -> penalty ~0.30-0.40
    assert 0.25 <= result["penalty_multiplier"] <= 0.45, (
        f"Expected ~0.30-0.40, got {result['penalty_multiplier']}"
    )
    assert "Vague Buzzwords" in result["reason"]