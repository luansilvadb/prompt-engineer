import torch
from unittest.mock import patch, MagicMock
from src.evaluators import calculate_semantic_penalty, get_embedder


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mock_embedder(sim_value: float):
    """
    Returns a mock SentenceTransformer instance whose encode() always produces
    tensors that yield a cosine similarity of `sim_value` when compared.

    Strategy: produce orthogonal-ish unit tensors and let torch compute real cosine
    similarity. We achieve a target sim by using:
      - vec_a = [1, 0]
      - vec_b = [cos(θ), sin(θ)]  where θ = arccos(sim_value)
    """
    import math
    theta = math.acos(max(-1.0, min(1.0, sim_value)))
    vec_a = torch.zeros(384)
    vec_a[0] = 1.0
    vec_b = torch.zeros(384)
    vec_b[0] = math.cos(theta)
    vec_b[1] = math.sin(theta)

    call_count = [0]

    def fake_encode(text, convert_to_tensor=True):
        call_count[0] += 1
        return vec_a if call_count[0] % 2 == 1 else vec_b

    mock = MagicMock()
    mock.encode.side_effect = fake_encode
    return mock


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_singleton_loading():
    """get_embedder() must always return the same instance (singleton pattern)."""
    with patch('src.semantic_evaluator.SentenceTransformer') as mock_st:
        mock_st.return_value = MagicMock()
        # Reset singleton so our mock is used
        import src.semantic_evaluator as sem
        original = sem._embedder
        sem._embedder = None
        try:
            embedder1 = get_embedder()
            embedder2 = get_embedder()
            assert embedder1 is embedder2
            assert mock_st.call_count == 1  # model loaded only once
        finally:
            sem._embedder = original  # restore previous state


def test_no_penalty():
    """Texts with cosine similarity well below the threshold get penalty = 1.0."""
    # sim = 0.3 → far below the default threshold of 0.85 → no penalty
    mock_embedder = _make_mock_embedder(0.3)
    with patch('src.semantic_evaluator._embedder', mock_embedder):
        penalty = calculate_semantic_penalty("text1", "text2", threshold=0.85)
    assert penalty == 1.0


def test_continuous_decay():
    """Texts with similarity just above threshold should return a value in (0.01, 1.0)."""
    # sim = 0.92 → slightly above 0.85 → quadratic decay kicks in
    mock_embedder = _make_mock_embedder(0.92)
    with patch('src.semantic_evaluator._embedder', mock_embedder):
        penalty = calculate_semantic_penalty("text1", "text2", threshold=0.85)
    assert 0.01 <= penalty < 1.0, f"Expected decay, got penalty={penalty}"


def test_max_penalty():
    """Identical texts (sim=1.0) should get the minimum possible penalty (0.01)."""
    # sim = 1.0 → max cosine → maximum decay → floor at 0.01
    mock_embedder = _make_mock_embedder(1.0)
    with patch('src.semantic_evaluator._embedder', mock_embedder):
        penalty = calculate_semantic_penalty("same text", "same text", threshold=0.85)
    assert penalty == 0.01, f"Expected minimum penalty 0.01, got {penalty}"

