import textstat

from src.evaluators.buzzwords import VAGUE_BUZZWORD_RE as _BUZZWORD_PATTERN
from src.evaluators.density import compute_lexical_density
textstat.set_lang('pt')

_BUZZWORD_THRESHOLD = 3  # ≥ N ocorrências → penalidade

def evaluate_heuristics(
    text: str,
    density_min: float = 0.35,
    penalty_factor: float = 0.85,
    buzzword_threshold: int = _BUZZWORD_THRESHOLD,
) -> dict:
    word_count = textstat.lexicon_count(text)

    # Short texts bypass filters
    if word_count < 30:
        return {"prune": False, "penalty_multiplier": 1.0, "reason": "Bypassed (short text)"}

    # Layer 0: Vague Buzzword Detection
    # Penalidade progressiva: 3 buzzwords = 0.9x, 5 = 0.7x, 10+ = 0.3x.
    # Evita o cliff edge onde 3 buzzwords derrubavam o reward para 0.15.
    buzzword_hits = _BUZZWORD_PATTERN.findall(text)
    if len(buzzword_hits) >= buzzword_threshold:
        unique_hits = list(dict.fromkeys(h.lower() for h in buzzword_hits))
        excess = len(buzzword_hits) - buzzword_threshold + 1
        progressive_penalty = max(0.30, 1.0 - 0.10 * excess)
        return {
            "prune": False,
            "penalty_multiplier": progressive_penalty,
            "reason": f"Vague Buzzwords ({len(buzzword_hits)} hits: {unique_hits[:5]})",
        }

    # Layer 1: Lexical Density (Type-Token Ratio)
    unique_ratio = compute_lexical_density(text)

    # Hard prune if highly repetitive (hollow verbosity)
    if unique_ratio < density_min:
        return {"prune": True, "penalty_multiplier": 0.0, "reason": "Low Lexical Density"}

    # Layer 2: Readability combined penalty
    # Penalize if it's very long but very simple (high Flesch Reading Ease means easy)
    reading_ease = textstat.flesch_reading_ease(text)

    multiplier = 1.0
    if word_count > 200 and reading_ease > 80:
        # Long and overly simple text gets penalized
        multiplier = penalty_factor

    return {"prune": False, "penalty_multiplier": multiplier, "reason": "Passed"}
