"""Density Evaluator — COGN-04: Densificação Extrema. Calculates a density multiplier that rewards compressed, logically-structured instructions over verbose chain-of-thought."""

import re
from src.domain.quality_interfaces import DensityContext, DensityResult

class DensityResultFloat(float):
    """Subclass of float that matches DensityResult interface for backward compatibility."""
    def __new__(cls, multiplier: float, child_density: float, parent_density: float, is_neutral: bool, reason: str):
        inst = super().__new__(cls, multiplier)
        inst.multiplier = multiplier
        inst.child_density = child_density
        inst.parent_density = parent_density
        inst.is_neutral = is_neutral
        inst.reason = reason
        return inst

def compute_lexical_density(text: str) -> float:
    clean_text = re.sub(r'[^\w\s]', '', text.lower())
    tokens = clean_text.split()
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)

def _has_structured_fields(instruction: str) -> bool:
    normalized = instruction.lower()
    required = ["## raciocínio", "## regras", "## conclusão"]
    return all(s in normalized for s in required)

class DensityMultiplier:
    def calculate(
        self,
        context: DensityContext,
        mutation_strategy: str = "",
        base_threshold: float = 1.0,
    ) -> DensityResult:
        child_len = len(context.child_instruction)
        parent_len = len(context.parent_instruction)
        
        child_density = compute_lexical_density(context.child_instruction)
        parent_density = compute_lexical_density(context.parent_instruction)
        
        # RN-05: Multiplicador DEVE ser 1.0 se:
        # - min_density_threshold == 0.0 (desabilitado)
        if context.min_density_threshold == 0.0:
            return DensityResult(
                multiplier=1.0,
                child_density=child_density,
                parent_density=parent_density,
                is_neutral=True,
                reason="Min density threshold is disabled (0.0)"
            )
            
        # - len(child_instruction) == len(parent_instruction) (sem mudança)
        if child_len == parent_len:
            if mutation_strategy == "mutador_cognitivo" and _has_structured_fields(context.child_instruction):
                mult = base_threshold + context.structured_bonus
                mult = max(context.multiplier_min, min(context.multiplier_max, mult))
                return DensityResult(
                    multiplier=mult,
                    child_density=child_density,
                    parent_density=parent_density,
                    is_neutral=False,
                    reason="Cognitive structured bonus applied at equal length"
                )
            return DensityResult(
                multiplier=base_threshold,
                child_density=child_density,
                parent_density=parent_density,
                is_neutral=True,
                reason="Same length instructions"
            )
            
        parent_len_val = max(1, parent_len)
        compression_ratio = child_len / parent_len_val
        
        # Base formula: base_threshold / compression_ratio
        multiplier = base_threshold / max(0.01, compression_ratio)
        multiplier = max(context.multiplier_min, min(context.multiplier_max, multiplier))
        
        # Cognitive structured bonus
        if mutation_strategy == "mutador_cognitivo" and _has_structured_fields(context.child_instruction):
            multiplier += context.structured_bonus
            multiplier = max(context.multiplier_min, min(context.multiplier_max, multiplier))
            
        return DensityResult(
            multiplier=multiplier,
            child_density=child_density,
            parent_density=parent_density,
            is_neutral=False,
            reason="Compression/expansion multiplier applied"
        )

def calculate_density_multiplier(
    child_instruction: str,
    parent_instruction: str,
    mutation_strategy: str = "",
    density_threshold: float = 1.0,
    density_multiplier_min: float = 0.5,
    density_multiplier_max: float = 1.5,
    structured_bonus: float = 0.2,
    min_density: float = 0.35,
) -> DensityResultFloat:
    """
    Calcula multiplicador de densidade que recompensa compressão e penaliza verbosidade.
    Conforma com o protocolo IDensityMultiplier usando DensityContext e DensityResult.
    """
    context = DensityContext(
        child_instruction=child_instruction,
        parent_instruction=parent_instruction,
        min_density_threshold=min_density,
        multiplier_min=density_multiplier_min,
        multiplier_max=density_multiplier_max,
        structured_bonus=structured_bonus,
    )
    result = DensityMultiplier().calculate(
        context,
        mutation_strategy=mutation_strategy,
        base_threshold=density_threshold,
    )
    return DensityResultFloat(
        multiplier=result.multiplier,
        child_density=result.child_density,
        parent_density=result.parent_density,
        is_neutral=result.is_neutral,
        reason=result.reason,
    )
