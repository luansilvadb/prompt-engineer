import torch
from sentence_transformers import SentenceTransformer, util

# Global singleton to avoid reloading the model
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _embedder

def calculate_semantic_penalty(text1: str, text2: str, threshold: float = 0.85) -> float:
    model = get_embedder()
    
    # Truncate string sizes to prevent OOM (Security Domain requirement)
    text1 = text1[:2048]
    text2 = text2[:2048]
    
    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)
    
    # Extract scalar to avoid memory leaks in the MCTS loop
    cosine_sim = util.cos_sim(emb1, emb2).item()
    
    if cosine_sim <= threshold:
        return 1.0 # No penalty
        
    # Quadratic decay mapping [threshold, 1.0] -> [1.0, 0.0]
    penalty = 1.0 - ((cosine_sim - threshold) / (1.0 - threshold)) ** 2
    return max(0.01, float(penalty))
