"""Density Evaluator — COGN-04: Densificação Extrema. Calculates a density multiplier that rewards compressed, logically-structured instructions over verbose chain-of-thought."""

import re


def compute_lexical_density(text: str) -> float:
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    tokens = clean_text.split()
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def _has_structured_fields(instruction: str) -> bool:
    normalized = instruction.lower()
    return all(s in normalized for s in ("## raciocínio", "## regras", "## conclusão"))


def calculate_density_multiplier(
    child_instruction: str,
    parent_instruction: str,
    mutation_strategy: str = "",
    density_threshold: float = 1.0,
    density_multiplier_min: float = 0.5,
    density_multiplier_max: float = 1.5,
    structured_bonus: float = 0.2,
    min_density: float = 0.35,
) -> float:
    """Calcula multiplicador de densidade que recompensa compressão e penaliza verbosidade."""
    child_len, parent_len = len(child_instruction), len(parent_instruction)

    if min_density == 0.0:
        return 1.0

    if child_len == parent_len:
        if mutation_strategy == "mutador_cognitivo" and _has_structured_fields(child_instruction):
            return max(density_multiplier_min, min(density_multiplier_max, density_threshold + structured_bonus))
        return density_threshold

    multiplier = density_threshold / max(0.01, child_len / max(1, parent_len))
    multiplier = max(density_multiplier_min, min(density_multiplier_max, multiplier))

    if mutation_strategy == "mutador_cognitivo" and _has_structured_fields(child_instruction):
        multiplier = max(density_multiplier_min, min(density_multiplier_max, multiplier + structured_bonus))

    return multiplier
