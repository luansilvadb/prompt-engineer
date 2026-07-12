"""
Experience Store — Dyna-2 Long-term Memory

Persiste aprendizados entre execuções do otimizador.
Cada experiência registra: qual mutação foi aplicada, qual delta de reward produziu,
e o feedback do juiz. Retrieval por similaridade via TF-IDF sobre os feedbacks.

Referência: David Silver, Dyna-2 Architecture —
"general domain knowledge from past interactions" (long-term memory)
"""

import json
import math
import hashlib
import re
import time
from pathlib import Path
from typing import List, Dict
from collections import Counter

EXPERIENCES_DIR = Path('src/outputs/experiences')

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


# ─────────────────────────────────────────────
# Experience Store
# ─────────────────────────────────────────────

class ExperienceStore:
    """
    Armazena e recupera experiências de otimizações passadas.
    Persistência via JSON Lines. Retrieval via TF-IDF sobre feedbacks.
    Temporal decay (γ) reduz peso de experiências antigas.
    """

    def __init__(self, gamma: float = 0.995, max_experiences: int = 500):
        self.gamma = gamma
        self.max_experiences = max_experiences
        self.experiences: List[Experience] = []
        self._load()

    def _store_path(self) -> Path:
        EXPERIENCES_DIR.mkdir(parents=True, exist_ok=True)
        return EXPERIENCES_DIR / 'experience_log.jsonl'

    def _load(self):
        path = self._store_path()
        if not path.exists():
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.experiences.append(Experience.from_dict(json.loads(line)))
        except Exception:
            pass  # Arquivo corrompido — começar limpo

    def save(self):
        """Persiste todas as experiências em disco (reescrita atômica)."""
        path = self._store_path()
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                for exp in self.experiences[-self.max_experiences:]:
                    f.write(json.dumps(exp.to_dict(), ensure_ascii=False) + '\n')
            import os
            os.replace(temp_path, path)
        except Exception:
            pass

    def add(self, experience: Experience):
        self.experiences.append(experience)
        # Truncar se exceder o limite
        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences:]

    def query_similar(self, feedback_query: str, top_k: int = 5) -> List[Experience]:
        """
        Busca experiências com feedback similar usando TF-IDF + cosine similarity.
        Aplica temporal decay: experiências mais antigas têm peso reduzido.
        """
        if not self.experiences:
            return []

        query_tokens = _tokenize(feedback_query)
        if not query_tokens:
            return self.experiences[-top_k:]

        # Construir corpus de tokens
        all_doc_tokens = [_tokenize(exp.feedback) for exp in self.experiences]
        all_doc_tokens.append(query_tokens)

        idf = _compute_idf(all_doc_tokens)

        # TF-IDF da query
        query_tf = _compute_tf(query_tokens)
        query_tfidf = {word: tf * idf.get(word, 1.0) for word, tf in query_tf.items()}

        # Calcular similaridade com decay temporal
        now = time.time()
        scored = []
        for i, exp in enumerate(self.experiences):
            doc_tf = _compute_tf(all_doc_tokens[i])
            doc_tfidf = {word: tf * idf.get(word, 1.0) for word, tf in doc_tf.items()}
            sim = _cosine_similarity(query_tfidf, doc_tfidf)

            # Temporal decay: exp mais antigas perdem peso
            age_days = (now - exp.timestamp) / 86400.0
            decay = self.gamma ** age_days
            scored.append((sim * decay, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:top_k]]

    def get_strategy_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Retorna estatísticas por mutation_strategy:
        {strategy: {mean_delta, count, total_reward}}
        Usado pelo multi-armed bandit de mutations.
        """
        stats: Dict[str, Dict[str, float]] = {}
        for exp in self.experiences:
            key = exp.mutation_strategy
            if key not in stats:
                stats[key] = {'total_delta': 0.0, 'count': 0, 'total_reward': 0.0}
            stats[key]['total_delta'] += exp.delta_reward
            stats[key]['count'] += 1
            stats[key]['total_reward'] += exp.absolute_reward

        for key in stats:
            count = stats[key]['count']
            stats[key]['mean_delta'] = stats[key]['total_delta'] / max(1, count)

        return stats


def hash_instruction(text: str) -> str:
    """Hash determinístico de uma instrução para uso como ID."""
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()[:16]
