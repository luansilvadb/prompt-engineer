import textstat
import re
from typing import List

textstat.set_lang('pt')

# ── Vague Buzzword Filter (Layer 0) ──────────────────────────────────────────
# Clichês e buzzwords de escrita de IA generativa que sinalizam verbosidade oca.
# Fonte empírica: padrões recorrentes em outputs de LLMs sem cadeia de raciocínio.
_VAGUE_BUZZWORDS: List[str] = [
    # Inglês — marcadores de texto AI genérico
    r"\bdelve\b", r"\btestament\b", r"\bin conclusion\b", r"\bmoreover\b",
    r"\bfurthermore\b", r"\bnevertheless\b", r"\bit(?:'s| is) worth noting\b",
    r"\bit(?:'s| is) important to note\b", r"\bin summary\b", r"\bin essence\b",
    r"\bto summarize\b", r"\bpivotal\b", r"\blandscape\b", r"\bparadigm\b",
    r"\bseamless(?:ly)?\b", r"\brobust\b", r"\bleverage\b", r"\bsynergy\b",
    r"\bgroundbreaking\b", r"\bstate-of-the-art\b", r"\bcutting-edge\b",
    # Português — equivalentes de verbosidade oca
    r"\bem suma\b", r"\bem conclusão\b", r"\bcabe ressaltar\b",
    r"\bé importante destacar\b", r"\bé fundamental ressaltar\b",
    r"\bno contexto atual\b", r"\bno cenário atual\b",
    r"\bde extrema importância\b", r"\bvalioso\b",
]
_BUZZWORD_PATTERN = re.compile("|".join(_VAGUE_BUZZWORDS), re.IGNORECASE)
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
    # Textos com muitos clichês de IA recebem penalidade severa sem gastar tokens no juiz.
    buzzword_hits = _BUZZWORD_PATTERN.findall(text)
    if len(buzzword_hits) >= buzzword_threshold:
        unique_hits = list(dict.fromkeys(h.lower() for h in buzzword_hits))
        return {
            "prune": False,
            "penalty_multiplier": 0.15,
            "reason": f"Vague Buzzwords ({len(buzzword_hits)} hits: {unique_hits[:5]})",
        }

    # Layer 1: Lexical Density (Type-Token Ratio)
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    tokens = clean_text.split()
    unique_ratio = len(set(tokens)) / max(1, len(tokens))

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
