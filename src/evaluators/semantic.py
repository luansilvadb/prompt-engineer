"""Avaliador semântico com cache LRU de embeddings para reduzir recomputação."""

from functools import lru_cache

from sentence_transformers import SentenceTransformer, util

# Global singleton to avoid reloading the model
_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _embedder


@lru_cache(maxsize=512)
def _cached_encode(text: str) -> bytes:
    """Cache LRU de embeddings serializados. Thread-safe (lru_cache built-in).

    Retorna bytes serializados para evitar que o tensor mantenha referências
    e cause memory leak no loop MCTS de longa duração.
    """
    model = get_embedder()
    text_truncated = text[:2048]
    emb = model.encode(text_truncated, convert_to_tensor=True)
    return emb.cpu().numpy().tobytes()


def _deserialize_embedding(data: bytes):
    """Reconstrói tensor a partir de bytes cacheados."""
    import numpy as np
    import torch

    arr = np.frombuffer(data, dtype=np.float32).copy()
    return torch.from_numpy(arr).unsqueeze(0)


def calculate_semantic_penalty(text1: str, text2: str, threshold: float = 0.85) -> float:
    """Calcula penalidade semântica com cache de embeddings."""

    # Cache hit para ambas as strings
    emb1_bytes = _cached_encode(text1)
    emb2_bytes = _cached_encode(text2)

    emb1 = _deserialize_embedding(emb1_bytes)
    emb2 = _deserialize_embedding(emb2_bytes)

    cosine_sim = util.cos_sim(emb1, emb2).item()

    if cosine_sim <= threshold:
        return 1.0  # No penalty

    # Quadratic decay mapping [threshold, 1.0] -> [1.0, 0.0]
    penalty = 1.0 - ((cosine_sim - threshold) / (1.0 - threshold)) ** 2
    return max(0.01, float(penalty))
