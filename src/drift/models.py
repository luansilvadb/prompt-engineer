"""
Drift Monitor — dataclasses de domínio.

Extrído de ``src/drift_monitor.py`` (L57-148 + bloco ``ProbeMeasurement``
L255-307) no plano 01-01 da fase 01-architectural-cleanup-densification.
Comportamento idêntico — apenas relocação para o novo namespace package
``src/drift/``.

Convenção de imutabilidade (Shared Pattern #7):
  - ``@dataclass(frozen=True)`` para value objects e config
    (``ProbeExpectation``, ``GoldenProbe``, ``DimensionError``,
    ``GateDecision``, ``DriftThresholds``).
  - ``@dataclass`` (mutável) para agregadores com listas
    (``DriftReport``, ``ProbeMeasurement``), usando
    ``field(default_factory=list)``.
"""

import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional

from src.signatures import Avaliacao, calcular_composite


# ─────────────────────────────────────────────
# Value objects (imutáveis)
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class ProbeExpectation:
    """Notas esperadas de um probe — aproximadas (α); só o ranking precisa estar correto."""
    manteve_regras_criticas: bool
    nota_clareza: float
    nota_formatacao: float
    nota_robustez: float
    nota_densidade_informacional: float
    nota_acionabilidade: float
    nota_anti_fragilidade: float

    def composite_score(self) -> float:
        # Reutiliza a tabela única de pesos (DRY — Norma 2).
        return calcular_composite(self)


@dataclass(frozen=True)
class GoldenProbe:
    id: str
    skill_original: str
    skill_otimizada: str
    regras_adicionais: str
    expected: ProbeExpectation
    expected_rank_band: str  # "alto" | "medio" | "baixo"
    verifier: str


@dataclass(frozen=True)
class DimensionError:
    dimension: str
    mae: float


# ─────────────────────────────────────────────
# Agregadores (mutáveis — field(default_factory=list))
# ─────────────────────────────────────────────

@dataclass
class DriftReport:
    judge_label: str
    spearman_composite: float
    offset_scale: float
    mae_per_dimension: List[DimensionError] = field(default_factory=list)
    critical_rules_concordance: float = 1.0  # diagnóstico (simétrico); não aciona veto
    critical_rules_violated: bool = False    # TRUE se missed_violations > 0 (veto direcional)
    missed_violations: int = 0               # juiz aprovou skill que viola regra (falha de segurança)
    false_rejections: int = 0                # juiz reprovou skill limpa (excesso de rigor; diagnóstico)
    mean_variance: float = 0.0
    repetitions: int = 0
    per_probe: List[dict] = field(default_factory=list)
    low_confidence: bool = False

    def to_dict(self) -> dict:
        return {
            'judge_label': self.judge_label,
            'spearman_composite': self.spearman_composite,
            'offset_scale': self.offset_scale,
            'mae_per_dimension': [{'dimension': d.dimension, 'mae': d.mae} for d in self.mae_per_dimension],
            'critical_rules_concordance': self.critical_rules_concordance,
            'critical_rules_violated': self.critical_rules_violated,
            'missed_violations': self.missed_violations,
            'false_rejections': self.false_rejections,
            'mean_variance': self.mean_variance,
            'repetitions': self.repetitions,
            'low_confidence': self.low_confidence,
            'per_probe': self.per_probe,
            'measured_at': time.time(),
        }


@dataclass
class ProbeMeasurement:
    probe_id: str
    samples: List[Avaliacao] = field(default_factory=list)

    def mean_composite(self) -> float:
        if not self.samples:
            return 0.0
        return statistics.mean(calcular_composite(s) for s in self.samples)

    def mean_per_dimension(self) -> dict:
        dims = ['nota_clareza', 'nota_formatacao', 'nota_robustez',
                'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade']
        out = {}
        for d in dims:
            vals = [getattr(s, d) for s in self.samples if s is not None]
            out[d] = statistics.mean(vals) if vals else 0.0
        return out

    def critical_rules_all_correct(self, expected: bool) -> bool:
        """True se TODAS as amostras concordam com o esperado para o hard-gate."""
        if not self.samples:
            return False
        return all((s.manteve_regras_criticas == expected) for s in self.samples if s is not None)

    def missed_violation_count(self, expected_critical: bool) -> int:
        """
        Conta amostras que APROVARAM uma skill que deveria reprovar.
        Direcional: só isto é falha de segurança (BR4). expected_critical=False
        significa que o probe é uma violação; se o juiz diz True, ele liberou.
        Tolerância zero: qualquer missed_violation = critical_rules_violated.
        """
        if expected_critical or not self.samples:
            return 0
        return sum(1 for s in self.samples if s is not None and s.manteve_regras_criticas)

    def false_rejection_count(self, expected_critical: bool) -> int:
        """
        Conta amostras que REPROVARAM uma skill limpa (excesso de rigor).
        Diagnóstico, não falha de segurança. expected_critical=True significa
        skill limpa; se o juiz diz False, ele foi rigoroso demais.
        """
        if not expected_critical or not self.samples:
            return 0
        return sum(1 for s in self.samples if s is not None and not s.manteve_regras_criticas)

    def variance(self) -> float:
        if len(self.samples) < 2:
            return 0.0
        composites = [calcular_composite(s) for s in self.samples if s is not None]
        if len(composites) < 2:
            return 0.0
        return statistics.pstdev(composites) * 100  # escala 0-100 p/ comparar com threshold


# ─────────────────────────────────────────────
# Config / decisions (imutáveis)
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class GateDecision:
    accept: bool
    reason: str
    triggered_metric: Optional[str] = None


@dataclass(frozen=True)
class DriftThresholds:
    spearman_floor: float = 0.8
    spearman_regression_margin: float = 0.05
    offset_alarm: float = 10.0
    offset_regression_margin: float = 3.0
    # critical_concordance_floor REMOVIDO: a métrica direcional (missed_violations > 0)
    # substitui o floor simétrico. Tolerância zero a falha de segurança — sem número mágico.
    variance_low_confidence: float = 8.0

    @classmethod
    def from_config(cls, cfg: dict) -> 'DriftThresholds':
        return cls(
            spearman_floor=cfg.get('spearman_floor', cls.spearman_floor),
            spearman_regression_margin=cfg.get('spearman_regression_margin', cls.spearman_regression_margin),
            offset_alarm=cfg.get('offset_alarm', cls.offset_alarm),
            offset_regression_margin=cfg.get('offset_regression_margin', cls.offset_regression_margin),
            variance_low_confidence=cfg.get('variance_low_confidence', cls.variance_low_confidence),
        )
