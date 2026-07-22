"""
Experience Store — Tipos compartilhados e helpers TF-IDF.

Define o modelo Experience e funções auxiliares (tokenização, TF-IDF,
hash) usadas tanto pelo backend SQLite quanto pelo optimizer.

O backend de armazenamento foi migrado para experience_store_sqlite.py.

Referência: David Silver, Dyna-2 Architecture —
"general domain knowledge from past interactions" (long-term memory)
"""

import math
import hashlib
import re
import time
from typing import List, Dict
from collections import Counter


# ─────────────────────────────────────────────
# Modelo de dados
# ─────────────────────────────────────────────

class Experience:
    __slots__ = (
        'skill_hash', 'mutation_strategy', 'delta_reward',
        'absolute_reward', 'feedback', 'timestamp', 'parent_instruction_hash',
        'instruction', 'parent_instruction'
    )

    def __init__(
        self,
        skill_hash: str,
        mutation_strategy: str,
        delta_reward: float,
        absolute_reward: float,
        feedback: str,
        timestamp: float = None,
        parent_instruction_hash: str = '',
        instruction: str = '',
        parent_instruction: str = ''
    ):
        self.skill_hash = skill_hash
        self.mutation_strategy = mutation_strategy
        self.delta_reward = delta_reward
        self.absolute_reward = absolute_reward
        self.feedback = feedback
        self.timestamp = timestamp or time.time()
        self.parent_instruction_hash = parent_instruction_hash
        self.instruction = instruction
        self.parent_instruction = parent_instruction

    def to_dict(self) -> dict:
        return {
            'skill_hash': self.skill_hash,
            'mutation_strategy': self.mutation_strategy,
            'delta_reward': self.delta_reward,
            'absolute_reward': self.absolute_reward,
            'feedback': self.feedback,
            'timestamp': self.timestamp,
            'parent_instruction_hash': self.parent_instruction_hash,
            'instruction': self.instruction,
            'parent_instruction': self.parent_instruction,
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'Experience':
        return cls(
            skill_hash=d['skill_hash'],
            mutation_strategy=d['mutation_strategy'],
            delta_reward=d['delta_reward'],
            absolute_reward=d['absolute_reward'],
            feedback=d['feedback'],
            timestamp=d.get('timestamp', 0.0),
            parent_instruction_hash=d.get('parent_instruction_hash', ''),
            instruction=d.get('instruction', ''),
            parent_instruction=d.get('parent_instruction', ''),
        )


# ─────────────────────────────────────────────
# TF-IDF simples (zero dependências externas)
# ─────────────────────────────────────────────

_STOP_WORDS = frozenset({
    'a', 'o', 'e', 'de', 'da', 'do', 'em', 'um', 'uma', 'que', 'para',
    'com', 'não', 'se', 'na', 'no', 'os', 'as', 'por', 'mais', 'é',
    'the', 'and', 'is', 'of', 'to', 'in', 'it', 'for', 'on', 'with',
    'as', 'at', 'by', 'an', 'be', 'or', 'was', 'are', 'but', 'not',
})

def _tokenize(text: str) -> List[str]:
    """Tokenização simples: lowercase, split em não-alfanuméricos, remove stop words."""
    tokens = re.findall(r'[a-záàâãéêíóôõúç]+', text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {word: count / total for word, count in counts.items()}


def _compute_idf(documents_tokens: List[List[str]]) -> Dict[str, float]:
    n_docs = len(documents_tokens)
    if n_docs == 0:
        return {}
    doc_freq = Counter()
    for tokens in documents_tokens:
        doc_freq.update(set(tokens))
    return {
        word: math.log((1 + n_docs) / (1 + freq)) + 1
        for word, freq in doc_freq.items()
    }


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    common_keys = set(vec_a.keys()) & set(vec_b.keys())
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def hash_instruction(text: str) -> str:
    """Hash determinístico de uma instrução para uso como ID."""
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()[:16]
