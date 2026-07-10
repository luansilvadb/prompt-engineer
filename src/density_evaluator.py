"""Density Evaluator — COGN-04: Densificação Extrema. Calculates a density multiplier that rewards compressed, logically-structured instructions over verbose chain-of-thought."""


def _has_structured_fields(instruction: str) -> bool:
    normalized = instruction.lower()
    required = ["## raciocínio", "## regras", "## conclusão"]
    return all(s in normalized for s in required)


def calculate_density_multiplier(
    child_instruction: str,
    parent_instruction: str,
    mutation_strategy: str = "",
    density_threshold: float = 1.0,
    density_multiplier_min: float = 0.5,
    density_multiplier_max: float = 1.5,
    structured_bonus: float = 0.2,
) -> float:
    parent_len = max(1, len(parent_instruction))
    compression_ratio = len(child_instruction) / parent_len
    density_mult = density_threshold / max(0.01, compression_ratio)
    density_mult = max(density_multiplier_min, min(density_multiplier_max, density_mult))
    if mutation_strategy == "mutador_cognitivo" and _has_structured_fields(child_instruction):
        density_mult += structured_bonus
    return density_mult
