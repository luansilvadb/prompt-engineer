from typing import Protocol
from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class QualityReport:
    linter_violations: int
    test_failures: int
    coverage_critical_modules: dict[str, float]
    complexity_violations: int
    is_approved: bool
    blocking_issues: list[str]

class IQualityGuard(Protocol):
    def validate_linter(self) -> bool:
        """RN-01: Retorna True se ruff check retorna 0 violations"""
        ...
    
    def validate_tests(self) -> bool:
        """RN-02: Retorna True se pytest retorna 0 failures"""
        ...
    
    def validate_coverage(self, threshold: float = 0.70) -> dict[str, float]:
        """RN-04: Retorna módulos críticos com cobertura < threshold"""
        ...
    
    def validate_complexity(self, max_cc: int = 15) -> list[tuple[str, int]]:
        """RN-03: Retorna funções com complexidade > max_cc"""
        ...
    
    def generate_report(self) -> QualityReport:
        """Agrega todas as validações"""
        ...


@dataclass(frozen=True)
class DensityContext:
    child_instruction: str
    parent_instruction: str
    min_density_threshold: float
    multiplier_min: float
    multiplier_max: float
    structured_bonus: float


@dataclass(frozen=True)
class DensityResult:
    multiplier: float
    child_density: float
    parent_density: float
    is_neutral: bool
    reason: str
    
    def __post_init__(self) -> None:
        if not (0.0 <= self.multiplier <= 2.0):
            raise ValueError(f"multiplier must be in [0.0, 2.0], got {self.multiplier}")
        if not (0.0 <= self.child_density <= 1.0):
            raise ValueError(f"child_density must be in [0.0, 1.0], got {self.child_density}")
        if not (0.0 <= self.parent_density <= 1.0):
            raise ValueError(f"parent_density must be in [0.0, 1.0], got {self.parent_density}")

# Alias para compatibilidade com o design doc seção 3.2
DensityMultiplierResult = DensityResult


class IDensityMultiplier(Protocol):
    def calculate(self, context: DensityContext) -> DensityResult:
        """
        RN-05: Multiplicador DEVE ser 1.0 se:
        - min_density_threshold == 0.0 (desabilitado)
        - len(child_instruction) == len(parent_instruction) (sem mudança)
        
        Invariante: multiplier ∈ [multiplier_min, multiplier_max]
        """
        ...


@dataclass(frozen=True)
class IterationResult:
    was_cancelled: bool
    node_expanded: bool
    reward_earned: float


class IMCTSCancellation(Protocol):
    def is_cancelled(self) -> bool:
        """Verifica flag de cancelamento"""
        ...
    
    def run_iteration(self) -> IterationResult:
        """
        RN-06: DEVE retornar imediatamente se is_cancelled() == True
        Checkpoints obrigatórios:
        1. Antes de selection
        2. Após expand
        3. Antes de simulation
        """
        ...


class GateDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    FAIL_OPEN = "fail_open"
    FAIL_CLOSED = "fail_closed"


@dataclass(frozen=True)
class DriftGateContext:
    candidate_instruction: str
    golden_set_path: str
    drift_thresholds: dict[str, float]


@dataclass(frozen=True)
class DriftGateResult:
    decision: GateDecision
    drift_score: float | None
    baseline_score: float | None
    reason: str


class IDriftGate(Protocol):
    def evaluate(self, context: DriftGateContext) -> DriftGateResult:
        """
        RN-07: Se medir_drift() lança exceção → FAIL_CLOSED (rejeição)
        RN-08: Se golden_set.is_empty() → FAIL_OPEN (aceite com warning)
        
        Invariante: decision sempre definido, nunca None
        """
        ...
