import textstat
import re

textstat.set_lang('pt')

def evaluate_heuristics(text: str, density_min: float = 0.35, penalty_factor: float = 0.85) -> dict:
    word_count = textstat.lexicon_count(text)
    
    # Short texts bypass filters
    if word_count < 30:
        return {"prune": False, "penalty_multiplier": 1.0, "reason": "Bypassed (short text)"}
        
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
