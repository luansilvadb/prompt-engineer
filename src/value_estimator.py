"""
Value Estimator — Predição de Recompensa via Bootstrapping

Estima a recompensa de uma skill sem chamar o juiz LLM,
usando features extraídas do texto + média exponencial móvel (EMA)
atualizada após cada avaliação real.

Silver: "Update a guess from a guess" — bootstrapping reduz variância.

Usado pelo MCTS para pré-filtrar candidatos ruins antes de gastar
chamadas LLM no juiz, permitindo 2-3x mais expansões no mesmo orçamento.
"""

import math
import re
from typing import Optional


# ─────────────────────────────────────────────
# Feature Extraction
# ─────────────────────────────────────────────

def _extract_features(text: str) -> dict:
    """
    Extrai features numéricas de uma skill para estimativa de qualidade.
    Retorna um dict de features normalizadas [0, 1].
    """
    lines = text.strip().split('\n')
    total_chars = len(text)
    total_lines = len(lines)

    # Densidade de markdown (headers, bold, lists)
    headers = sum(1 for l in lines if l.strip().startswith('#'))
    bolds = len(re.findall(r'\*\*[^*]+\*\*', text))
    lists = sum(1 for l in lines if re.match(r'^\s*[-*]\s', l))
    code_blocks = len(re.findall(r'```', text)) // 2

    # Comprimento normalizado (sweet spot: 1000-5000 chars)
    len_score = 1.0 - abs(min(max(total_chars, 500), 8000) - 3000) / 3000.0

    # Densidade estrutural (headers + listas por 100 linhas)
    structural_density = (headers + lists) / max(1, total_lines) * 10
    structural_score = min(1.0, structural_density)

    # Proporção de formatação rica
    format_elements = headers + bolds + lists + code_blocks
    format_score = min(1.0, format_elements / max(1, total_lines) * 5)

    # Anti "lost in the middle" — instruções no início e final
    first_quarter = text[:total_chars // 4]
    last_quarter = text[3 * total_chars // 4:]
    imperative_patterns = re.compile(
        r'\b(DEVE|NUNCA|SEMPRE|OBRIGATÓRIO|PROIBIDO|CRITICAL|MUST|NEVER|ALWAYS)\b',
        re.IGNORECASE
    )
    first_imperatives = len(imperative_patterns.findall(first_quarter))
    last_imperatives = len(imperative_patterns.findall(last_quarter))
    robustness_score = min(1.0, (first_imperatives + last_imperatives) / 6.0)

    # Diversidade de vocabulário (type-token ratio)
    words = re.findall(r'[a-záàâãéêíóôõúç]+', text.lower())
    ttr = len(set(words)) / max(1, len(words))
    diversity_score = min(1.0, ttr * 2)  # TTR típico ~0.3-0.6

    # Presença de seções essenciais
    has_examples = bool(re.search(r'(?:exemplo|example|ex:|e\.g\.)', text, re.IGNORECASE))
    has_antipatterns = bool(re.search(r'(?:anti.?padr|nunca|never|avoid|não faça)', text, re.IGNORECASE))
    completeness_score = (0.5 * int(has_examples) + 0.5 * int(has_antipatterns))

    return {
        'length': len_score,
        'structure': structural_score,
        'format': format_score,
        'robustness': robustness_score,
        'diversity': diversity_score,
        'completeness': completeness_score,
    }


# ─────────────────────────────────────────────
# Value Estimator
# ─────────────────────────────────────────────

class ValueEstimator:
    """
    Estima a recompensa esperada de uma skill baseada em features textuais.

    Mantém pesos aprendidos via EMA (Exponential Moving Average) online.
    Após cada avaliação real do juiz, atualiza os pesos para convergir
    a estimativa com a recompensa observada.
    """

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        # Pesos iniciais (prior uniform)
        self._weights = {
            'length': 0.15,
            'structure': 0.20,
            'format': 0.15,
            'robustness': 0.20,
            'diversity': 0.15,
            'completeness': 0.15,
        }
        self._bias = 0.3  # Prior conservador
        self._n_updates = 0

    def estimate(self, instruction: str) -> float:
        """
        Retorna a recompensa estimada [0, 1] para uma instrução.
        Não chama nenhuma API — puramente baseado em features textuais.
        """
        features = _extract_features(instruction)
        value = self._bias + sum(
            self._weights[k] * features[k] for k in self._weights
        )
        return max(0.0, min(1.0, value))

    def update(self, instruction: str, actual_reward: float):
        """
        Atualiza os pesos após observar a recompensa real do juiz.
        Usa gradient descent simples com EMA.
        """
        features = _extract_features(instruction)
        predicted = self.estimate(instruction)
        error = actual_reward - predicted

        # Atualizar pesos proporcionalmente ao erro e à feature
        for k in self._weights:
            self._weights[k] += self.learning_rate * error * features[k]
            # Clamp para evitar divergência
            self._weights[k] = max(-0.5, min(1.0, self._weights[k]))

        # Atualizar bias
        self._bias += self.learning_rate * error * 0.1
        self._bias = max(-0.5, min(1.0, self._bias))

        self._n_updates += 1

    @property
    def confidence(self) -> float:
        """
        Retorna a confiança do estimador [0, 1].
        Cresce com o número de updates (log-scale).
        """
        if self._n_updates == 0:
            return 0.0
        return min(1.0, math.log(1 + self._n_updates) / math.log(20))
