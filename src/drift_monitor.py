"""
Drift Monitor — Grounding da Recompensa (A1)

Âncora de calibração que quebra o loop de feedback positivo do teleprompter.
O juiz (AvaliadorDeSkill) era recompilado a partir das próprias experiências
que ele aprovava, sem nenhuma referência externa: um amplificador de viés com
realimentação positiva. Este módulo introduz:

  1. GoldenSet   — referência congelada (anchor pairs) lida em read-only.
  2. medir_drift — mede Spearman / offset / MAE / concordância de regras.
  3. DriftGate   — VETA regressões. Nunca otimiza em direção ao golden (BR1).
  4. circuit_breaker — rollback ao juiz zerado quando o hard-gate cai (BR4).

Princípio (Silver): a recompensa deve vir do ambiente, não da crença anterior
do agente. Aqui o "ambiente" é o golden set imutável.
"""

import json
import math
import os
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import dspy

from src.signatures import (
    Avaliacao,
    AvaliadorDeSkill,
    _invoke_judge_with,
    calcular_composite,
)

GOLDEN_DIR = Path('src/outputs/golden')
MODELS_DIR = Path('src/outputs/models')


# ─────────────────────────────────────────────
# Exceção de domínio
# ─────────────────────────────────────────────

class DriftMeasurementError(Exception):
    """Falha na medição de drift (LLM indisponível, JSON ilegível, etc.)."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


# ─────────────────────────────────────────────
# Dataclasses de domínio
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


# ─────────────────────────────────────────────
# GoldenSet — referência imutável (read-only em runtime)
# ─────────────────────────────────────────────

class GoldenSet:
    """
    Coleção congelada de probes. BR2: nunca entra no trainset do teleprompter.
    BR3: read-only em runtime; save() só em curadoria offline.
    """

    def __init__(self):
        self.version: str = ''
        self.curated_at: str = ''
        self.probes: List[GoldenProbe] = []
        self._load()

    def _store_path(self) -> Path:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        return GOLDEN_DIR / 'golden_set.json'

    def _load(self):
        path = self._store_path()
        if not path.exists():
            import sys
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                frozen_path = Path(sys._MEIPASS) / 'src' / 'outputs' / 'golden' / 'golden_set.json'
                if frozen_path.exists():
                    try:
                        import shutil
                        shutil.copy2(frozen_path, path)
                        print(f"[+] Golden set padrão restaurado localmente com sucesso em {path}")
                    except Exception as e:
                        path = frozen_path
                        print(f"[!] Falha ao criar golden set localmente: {e}. Usando do executável diretamente.")
        if not path.exists():
            print(f"[!] Golden set ausente em {path}. Portão operará em fail-open.")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.version = data.get('version', '')
            self.curated_at = data.get('curated_at', '')
            for pd in data.get('probes', []):
                exp = ProbeExpectation(**pd['expected'])
                self.probes.append(GoldenProbe(
                    id=pd['id'],
                    skill_original=pd['skill_original'],
                    skill_otimizada=pd['skill_otimizada'],
                    regras_adicionais=pd.get('regras_adicionais', ''),
                    expected=exp,
                    expected_rank_band=pd['expected_rank_band'],
                    verifier=pd.get('verifier', ''),
                ))
            print(f"[*] Golden set v{self.version} carregado: {len(self.probes)} probes.")
        except Exception as e:
            print(f"[!] Erro ao carregar golden set ({e}). Operando sem âncora.")
            self.probes = []

    def is_empty(self) -> bool:
        return len(self.probes) == 0

    def probe_by_id(self, probe_id: str) -> Optional[GoldenProbe]:
        for p in self.probes:
            if p.id == probe_id:
                return p
        return None

    def save(self, version: str, curated_at: str):
        """Persistência atômica — USAR APENAS EM CURADORIA OFFLINE (BR3)."""
        path = self._store_path()
        temp_path = path.with_suffix('.tmp')
        data = {
            'version': version,
            'curated_at': curated_at,
            'probes': [
                {
                    'id': p.id,
                    'skill_original': p.skill_original,
                    'skill_otimizada': p.skill_otimizada,
                    'regras_adicionais': p.regras_adicionais,
                    'expected': {
                        'manteve_regras_criticas': p.expected.manteve_regras_criticas,
                        'nota_clareza': p.expected.nota_clareza,
                        'nota_formatacao': p.expected.nota_formatacao,
                        'nota_robustez': p.expected.nota_robustez,
                        'nota_densidade_informacional': p.expected.nota_densidade_informacional,
                        'nota_acionabilidade': p.expected.nota_acionabilidade,
                        'nota_anti_fragilidade': p.expected.nota_anti_fragilidade,
                    },
                    'expected_rank_band': p.expected_rank_band,
                    'verifier': p.verifier,
                }
                for p in self.probes
            ],
        }
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)


# ─────────────────────────────────────────────
# ProbeMeasurement — agregado de repetições de um probe
# ─────────────────────────────────────────────

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
# JudgeProbeRunner — instância DSPy ISOLADA (R2)
# ─────────────────────────────────────────────

class JudgeProbeRunner:
    """
    Mede um juiz específico contra probes. Instancia seu PRÓPRIO
    dspy.Predict(AvaliadorDeSkill) — NUNCA referencia o módulo global
    avaliador_module (Norma 3, R2 verificado empiricamente: .demos é por-instância).
    """

    def __init__(self, label: str):
        self.label = label
        self._judge = dspy.Predict(AvaliadorDeSkill)

    def load_candidate(self, path: str) -> None:
        """Carrega few-shot compilado NESTA instância apenas."""
        try:
            self._judge.load(path)
        except Exception as e:
            raise DriftMeasurementError(
                f"Falha ao carregar juiz candidato de {path}",
                context={'judge_label': self.label, 'path': path, 'original': str(e)},
            )

    def as_zero(self) -> None:
        """Juiz zerado (sem few-shot) — baseline de drift-zero garantida por construção."""
        self._judge = dspy.Predict(AvaliadorDeSkill)

    def run(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        measurement = ProbeMeasurement(probe_id=probe.id)
        failures = 0
        for _ in range(repetitions):
            try:
                exemplo = dspy.Example(
                    skill_original=probe.skill_original,
                    regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                )
                predicao = dspy.Prediction(skill_otimizada=probe.skill_otimizada)
                avaliacao = _invoke_judge_with(self._judge, exemplo, predicao)
                measurement.samples.append(avaliacao)
            except Exception:
                failures += 1

        if len(measurement.samples) == 0:
            raise DriftMeasurementError(
                f"Todas as {repetitions} repetições falharam no probe {probe.id}",
                context={'judge_label': self.label, 'probe_id': probe.id, 'failures': failures},
            )
        return measurement


# ─────────────────────────────────────────────
# Spearman sem dependência externa
# ─────────────────────────────────────────────

def _spearman_rank_correlation(x: List[float], y: List[float]) -> float:
    """
    Correlação de postos de Spearman entre duas listas de mesmo comprimento.
    Implementação direta (sem scipy). Retorna 1.0 se n < 2 (sem ranking p/ corromper).
    Métrica REI do portão: pega Cenário 2 stealth (ranking trocado, notas estáveis).
    """
    n = len(x)
    if n < 2:
        return 1.0

    def ranks(values):
        order = sorted(range(n), key=lambda i: values[i])
        rank = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0  # postos 1-based
            for k in range(i, j + 1):
                rank[order[k]] = avg_rank
            i = j + 1
        return rank

    rx = ranks(x)
    ry = ranks(y)
    d2 = sum((rx[i] - ry[i]) ** 2 for i in range(n))
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


# ─────────────────────────────────────────────
# medir_drift — produz DriftReport
# ─────────────────────────────────────────────

def medir_drift(runner: JudgeProbeRunner, golden: GoldenSet, repetitions: int,
                thresholds: DriftThresholds) -> DriftReport:
    if golden.is_empty():
        raise DriftMeasurementError("Golden set vazio — nada a medir.")

    measurements: List[tuple] = []  # (probe, ProbeMeasurement)
    for probe in golden.probes:
        m = runner.run(probe, repetitions)
        measurements.append((probe, m))

    # Sequência por probe_id para parear esperado vs. previsto
    expected_composites = [p.expected.composite_score() for p, _ in measurements]
    predicted_composites = [m.mean_composite() for _, m in measurements]

    spearman = _spearman_rank_correlation(expected_composites, predicted_composites)
    offset_scale = (statistics.mean(predicted_composites) - statistics.mean(expected_composites)) * 100

    dims = ['nota_clareza', 'nota_formatacao', 'nota_robustez',
            'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade']
    mae_per_dim: List[DimensionError] = []
    for d in dims:
        diffs = []
        for p, m in measurements:
            exp_val = getattr(p.expected, d)
            pred_val = m.mean_per_dimension().get(d, 0.0)
            diffs.append(abs(pred_val - exp_val))
        mae_per_dim.append(DimensionError(dimension=d, mae=statistics.mean(diffs) if diffs else 0.0))

    # Concordância do hard-gate: fração de probes onde TODAS as amostras concordam.
    # Métrica SIMÉTRICA (diagnóstico). NÃO aciona veto sozinha.
    correct = sum(1 for p, m in measurements if m.critical_rules_all_correct(p.expected.manteve_regras_criticas))
    concordance = correct / len(measurements)

    # Métrica DIRECIONAL (veto, BR4): juiz aprovou skill que viola regra crítica?
    # Tolerância zero — qualquer missed_violation é falha de segurança.
    total_missed = sum(m.missed_violation_count(p.expected.manteve_regras_criticas) for p, m in measurements)
    total_false_rej = sum(m.false_rejection_count(p.expected.manteve_regras_criticas) for p, m in measurements)
    critical_violated = total_missed > 0

    variances = [m.variance() for _, m in measurements]
    mean_var = statistics.mean(variances) if variances else 0.0
    low_conf = mean_var > thresholds.variance_low_confidence

    per_probe = []
    for p, m in measurements:
        per_probe.append({
            'probe_id': p.id,
            'expected_composite': p.expected.composite_score(),
            'predicted_composite': m.mean_composite(),
            'variance': m.variance(),
            'expected_critical': p.expected.manteve_regras_criticas,
            'observed_critical_all_correct': m.critical_rules_all_correct(p.expected.manteve_regras_criticas),
            'missed_violations': m.missed_violation_count(p.expected.manteve_regras_criticas),
            'false_rejections': m.false_rejection_count(p.expected.manteve_regras_criticas),
        })

    return DriftReport(
        judge_label=runner.label,
        spearman_composite=spearman,
        offset_scale=offset_scale,
        mae_per_dimension=mae_per_dim,
        critical_rules_concordance=concordance,
        critical_rules_violated=critical_violated,
        missed_violations=total_missed,
        false_rejections=total_false_rej,
        mean_variance=mean_var,
        repetitions=repetitions,
        per_probe=per_probe,
        low_confidence=low_conf,
    )


# ─────────────────────────────────────────────
# DriftGate — VETA regressões, NUNCA otimiza (BR1)
# ─────────────────────────────────────────────

class DriftGate:
    """
    Portão defensivo hierárquico:
      Passo 1 — Veto absoluto (BR4): concordância de regras críticas.
      Passo 2 — Confiança: variância alta exige melhoria estrita.
      Passo 3 — Spearman (Cenário 2 stealth): métrica rei.
      Passo 4 — Offset (Cenário 1 inflação): alarme.
    """

    @staticmethod
    def avaliar_candidato(report_cand: DriftReport,
                          report_atual: Optional[DriftReport],
                          thresholds: DriftThresholds) -> GateDecision:
        # Passo 1 — Veto absoluto: juiz aprovou skill que viola regra crítica (BR4 direcional).
        # Tolerância zero a missed_violations (falha de segurança). Sem número mágico/floor.
        if report_cand.critical_rules_violated:
            return GateDecision(
                False,
                f"juiz aprovou {report_cand.missed_violations} violacao(oes) de regras criticas (missed_violations > 0)",
                "critical_rules",
            )

        strict_required = report_cand.low_confidence

        def _strict_better_or_reject(metric_cand, metric_atual, better_when_lower: bool, metric_name: str, reason_msg: str):
            if report_atual is None:
                return None  # sem baseline, só floor absoluto
            if better_when_lower:
                if metric_cand > metric_atual:
                    return GateDecision(False, reason_msg, metric_name)
            else:
                if metric_cand < metric_atual:
                    return GateDecision(False, reason_msg, metric_name)
            return None

        # Passo 3 — Spearman (métrica rei: pega troca de ranking stealth).
        if report_atual is not None:
            if report_cand.spearman_composite < report_atual.spearman_composite - thresholds.spearman_regression_margin:
                return GateDecision(
                    False,
                    f"regressao de ranking (spearman {report_cand.spearman_composite:.3f} vs atual {report_atual.spearman_composite:.3f})",
                    "spearman",
                )
        else:
            if report_cand.spearman_composite < thresholds.spearman_floor:
                return GateDecision(
                    False,
                    f"spearman abaixo do floor ({report_cand.spearman_composite:.3f} < {thresholds.spearman_floor})",
                    "spearman",
                )

        # Passo 4 — Offset (alarme de inflação — Cenário 1).
        if report_atual is not None:
            if report_cand.offset_scale > report_atual.offset_scale + thresholds.offset_regression_margin:
                return GateDecision(
                    False,
                    f"inflacao de nota (offset {report_cand.offset_scale:.2f} vs atual {report_atual.offset_scale:.2f})",
                    "offset",
                )
        else:
            if report_cand.offset_scale > thresholds.offset_alarm:
                return GateDecision(
                    False,
                    f"inflacao de nota acima do alarme (offset {report_cand.offset_scale:.2f} > {thresholds.offset_alarm})",
                    "offset",
                )

        # Passo 2 (aviso) — baixa confiança não rejeita, mas exige estrita melhoria
        # (ja validado acima: qualquer regressão rejeita; em baixa confiança, margens
        # já são mais duras porque não há tolerância extra).
        if report_cand.low_confidence:
            return GateDecision(
                True,
                f"candidato aceito com BAIXA CONFIANCA (variancia {report_cand.mean_variance:.2f}); aumente DRIFT_REPETITIONS",
                None,
            )

        return GateDecision(True, "candidato nao regrediu", None)


# ─────────────────────────────────────────────
# Circuit breaker — rollback ao juiz zerado (BR4, KDD2)
# ─────────────────────────────────────────────

def verificar_juiz_atual(thresholds: DriftThresholds, repetitions: int) -> Optional[DriftReport]:
    """
    Mede o juiz atualmente em produção contra o golden. Retorna None se golden vazio.
    """
    golden = GoldenSet()
    if golden.is_empty():
        return None

    runner = JudgeProbeRunner("atual")
    model_path = MODELS_DIR / 'avaliador_otimizado.json'
    if model_path.exists():
        runner.load_candidate(str(model_path))
    else:
        runner.as_zero()

    return medir_drift(runner, golden, repetitions, thresholds)


def circuit_breaker(thresholds: DriftThresholds, repetitions: int) -> GateDecision:
    """
    Se o juiz atual comprometeu o hard-gate, renomeia o arquivo para
    .drifted.bak — fazendo load_avaliador() cair no juiz zerado (BR4).
    """
    report = verificar_juiz_atual(thresholds, repetitions)
    if report is None:
        return GateDecision(True, "golden ausente; nada a verificar", None)

    if report.critical_rules_violated:
        model_path = MODELS_DIR / 'avaliador_otimizado.json'
        if model_path.exists():
            ts = time.strftime('%Y%m%d_%H%M%S')
            backup = MODELS_DIR / f'avaliador_otimizado.drifted.{ts}.bak'
            try:
                os.replace(model_path, backup)
                print(f"[!] CIRCUIT BREAKER: juiz atual aprovou {report.missed_violations} violação(ões) "
                      f"de regras críticas (missed_violations > 0). Rollback ao juiz zerado. Backup em {backup.name}.")
            except Exception as e:
                print(f"[!] Circuit breaker: falha ao isolar juiz driftado ({e}).")
        return GateDecision(
            False,
            f"circuit breaker: rollback ao juiz zerado ({report.missed_violations} violações aprovadas)",
            "critical_rules",
        )

    extra = ""
    if report.false_rejections > 0:
        extra = f"; {report.false_rejections} false_rejections (excesso de rigor, diagnostico)"
    return GateDecision(True, f"juiz atual ok (spearman {report.spearman_composite:.3f}, offset {report.offset_scale:.2f}{extra})", None)


# ─────────────────────────────────────────────
# Cache do DriftReport do juiz atual (mitiga R1 — custo de LLM)
# ─────────────────────────────────────────────

def _drift_cache_path() -> Path:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    return MODELS_DIR / 'drift_cache.json'


def load_drift_cache() -> Optional[DriftReport]:
    path = _drift_cache_path()
    if not path.exists():
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return DriftReport(
            judge_label=data.get('judge_label', 'atual'),
            spearman_composite=data.get('spearman_composite', 1.0),
            offset_scale=data.get('offset_scale', 0.0),
            mae_per_dimension=[DimensionError(**d) for d in data.get('mae_per_dimension', [])],
            critical_rules_concordance=data.get('critical_rules_concordance', 1.0),
            critical_rules_violated=data.get('critical_rules_violated', False),
            missed_violations=data.get('missed_violations', 0),
            false_rejections=data.get('false_rejections', 0),
            mean_variance=data.get('mean_variance', 0.0),
            repetitions=data.get('repetitions', 0),
            low_confidence=data.get('low_confidence', False),
        )
    except Exception:
        return None


def save_drift_cache(report: DriftReport) -> None:
    """Persistência atômica do DriftReport do juiz em produção."""
    path = _drift_cache_path()
    temp_path = path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    except Exception as e:
        print(f"[!] Falha ao salvar drift cache ({e}).")
