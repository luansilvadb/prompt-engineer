import time
import dspy
from src.infrastructure.dspy_impl import AvaliadorDeSkillSignature, _invoke_judge_with, AvaliadorModoBSignature, _invoke_judge_modo_b_with
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import ProbeMeasurement, GoldenProbe

# ── Fail-fast em cascata de infra ─────────────────────────────────────────────
# Substrings (lowercase) que caracterizam FALHA DE INFRA. Detectadas via
# _classify_exception() — abortam o runner antes de esgotar repetitions × probes.
# Erros de parse/qualidade (JSON malformado, campo ausente, nota não-numérica)
# NÃO estão aqui e não contam para fail-fast (são isolados por probe).
_INFRA_ERROR_PATTERNS = (
    'timeout', 'timed out',                    # Timeout (90s do LiteLLM)
    'connection', 'refused', 'unreachable',    # Conexão/rede
    'unauthorized', '401', 'authentication',   # Auth
    'rate limit', '429',                       # Rate limit (transitório — se persiste, aborta)
    'api_key', 'api key', 'no api',           # API key ausente
    'overloaded', '503', '504',               # Servidor sobrecarga
)

# Aborta se ocorrer primeiro:
_MAX_INFRA_FAILURES = 3          # ≥3 falhas consecutivas de infra
_MAX_INFRA_ELAPSED_SECONDS = 60  # ou >60s decorridos acumulando falhas de infra


def _classify_exception(exc: Exception) -> tuple:
    """
    Classifica uma exceção em ('infra', pattern_match) ou ('parse', None).
    'infra' = falha de infraestrutura (rede/auth/timeout/sobrecarga) → fail-fast.
    'parse' = falha de qualidade (JSON/campo/nota) → isolada, não aborta.
    """
    msg = str(exc).lower()
    for pattern in _INFRA_ERROR_PATTERNS:
        if pattern in msg:
            return ('infra', pattern)
    return ('parse', None)


def _abort_fail_fast(consecutive_infra: int, elapsed: float, probe_id: str, label: str) -> None:
    """Levanta DriftMeasurementError se os critérios de fail-fast forem atingidos."""
    reason = None
    if consecutive_infra >= _MAX_INFRA_FAILURES:
        reason = 'infra_failures_consecutive'
    elif elapsed > _MAX_INFRA_ELAPSED_SECONDS:
        reason = 'infra_failures_elapsed'
    if reason is not None:
        raise DriftMeasurementError(
            f"Fail-fast disparado no probe {probe_id}: {consecutive_infra} falha(s) consecutivas de infra "
            f"em {elapsed:.1f}s ({reason}). API indisponível ou mal configurada.",
            context={
                'judge_label': label,
                'probe_id': probe_id,
                'abort_reason': reason,
                'consecutive_infra': consecutive_infra,
                'elapsed_seconds': elapsed,
            },
        )


class JudgeProbeRunner:
    """
    Mede um juiz específico contra probes. Instancia seu PRÓPRIO
    dspy.Predict(AvaliadorDeSkill) — NUNCA referencia o módulo global
    avaliador_module (Norma 3, R2 verificado empiricamente: .demos é por-instância).
    """

    def __init__(self, label: str):
        self.label = label
        self._judge = dspy.Predict(AvaliadorDeSkillSignature)
        self._judge_modo_b = dspy.Predict(AvaliadorModoBSignature)

    def load_candidate(self, path: str) -> None:
        """Carrega few-shot compilado NESTA instância apenas (Modo A)."""
        try:
            self._judge.load(path)
        except Exception as e:
            raise DriftMeasurementError(
                f"Falha ao carregar juiz candidato de {path}",
                context={'judge_label': self.label, 'path': path, 'original': str(e)},
            )

    def load_candidate_modo_b(self, path: str) -> None:
        """Carrega few-shot compilado NESTA instância apenas (Modo B)."""
        try:
            self._judge_modo_b.load(path)
        except Exception as e:
            raise DriftMeasurementError(
                f"Falha ao carregar juiz candidato (Modo B) de {path}",
                context={'judge_label': self.label, 'path': path, 'original': str(e)},
            )

    def as_zero(self) -> None:
        """Juiz zerado (sem few-shot) — baseline de drift-zero garantida por construção (Modo A)."""
        self._judge = dspy.Predict(AvaliadorDeSkillSignature)

    def as_zero_modo_b(self) -> None:
        """Juiz zerado (sem few-shot) — baseline de drift-zero garantida por construção (Modo B)."""
        self._judge_modo_b = dspy.Predict(AvaliadorModoBSignature)

    def _run_with_fail_fast(self, probe: GoldenProbe, repetitions: int, invoke_fn, modo: str) -> ProbeMeasurement:
        """
        Loop de medição com fail-fast em cascata de infra. Centraliza a lógica
        compartilhada entre Modo A e Modo B (DRY). Erros de parse são isolados
        por probe; erros de infra acumulam e disparam abort se atingirem os
        critérios (_MAX_INFRA_FAILURES ou _MAX_INFRA_ELAPSED_SECONDS).
        """
        measurement = ProbeMeasurement(probe_id=probe.id)
        failures = 0
        consecutive_infra = 0
        first_infra_at = None

        for _ in range(repetitions):
            try:
                exemplo = dspy.Example(
                    skill_original=probe.skill_original,
                    regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                )
                predicao = dspy.Prediction(skill_otimizada=probe.skill_otimizada)
                avaliacao = invoke_fn(exemplo, predicao)
                measurement.samples.append(avaliacao)
                consecutive_infra = 0  # sucesso reseta a contagem consecutiva
                first_infra_at = None
            except Exception as e:
                failures += 1
                kind, pattern = _classify_exception(e)
                if kind == 'infra':
                    now = time.monotonic()
                    if first_infra_at is None:
                        first_infra_at = now
                    consecutive_infra += 1
                    elapsed = now - first_infra_at
                    # Fail-fast: aborta antes de esgotar repetitions × probes × timeout.
                    _abort_fail_fast(consecutive_infra, elapsed, probe.id, self.label)
                # Erro de parse: isolado por probe, não aborta, continua tentando.

        if len(measurement.samples) == 0:
            raise DriftMeasurementError(
                f"Todas as {repetitions} repetições falharam no probe {probe.id} (Modo {modo.upper()})",
                context={'judge_label': self.label, 'probe_id': probe.id, 'failures': failures},
            )
        return measurement

    def run_modo_a(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        return self._run_with_fail_fast(probe, repetitions, lambda ex, pred: _invoke_judge_with(self._judge, ex, pred), 'a')

    def run_modo_b(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        return self._run_with_fail_fast(probe, repetitions, lambda ex, pred: _invoke_judge_modo_b_with(self._judge_modo_b, ex, pred), 'b')

    def run(self, probe: GoldenProbe, repetitions: int, modo: str = 'b') -> ProbeMeasurement:
        """Por padrão, toda avaliação usa o Modo B (D-03)."""
        if modo == 'a':
            return self.run_modo_a(probe, repetitions)
        elif modo == 'b':
            return self.run_modo_b(probe, repetitions)
        else:
            raise ValueError(f"Modo desconhecido: {modo}")