import dspy
from src.signatures import AvaliadorDeSkill, Avaliacao, _invoke_judge_with, AvaliadorModoB, _invoke_judge_modo_b_with
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import ProbeMeasurement, GoldenProbe

class JudgeProbeRunner:
    """
    Mede um juiz específico contra probes. Instancia seu PRÓPRIO
    dspy.Predict(AvaliadorDeSkill) — NUNCA referencia o módulo global
    avaliador_module (Norma 3, R2 verificado empiricamente: .demos é por-instância).
    """

    def __init__(self, label: str):
        self.label = label
        self._judge = dspy.Predict(AvaliadorDeSkill)
        self._judge_modo_b = dspy.Predict(AvaliadorModoB)

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
        self._judge = dspy.Predict(AvaliadorDeSkill)

    def as_zero_modo_b(self) -> None:
        """Juiz zerado (sem few-shot) — baseline de drift-zero garantida por construção (Modo B)."""
        self._judge_modo_b = dspy.Predict(AvaliadorModoB)

    def run_modo_a(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
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
                f"Todas as {repetitions} repetições falharam no probe {probe.id} (Modo A)",
                context={'judge_label': self.label, 'probe_id': probe.id, 'failures': failures},
            )
        return measurement

    def run_modo_b(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        measurement = ProbeMeasurement(probe_id=probe.id)
        failures = 0
        for _ in range(repetitions):
            try:
                exemplo = dspy.Example(
                    skill_original=probe.skill_original,
                    regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                )
                predicao = dspy.Prediction(skill_otimizada=probe.skill_otimizada)
                avaliacao = _invoke_judge_modo_b_with(self._judge_modo_b, exemplo, predicao)
                measurement.samples.append(avaliacao)
            except Exception:
                failures += 1

        if len(measurement.samples) == 0:
            raise DriftMeasurementError(
                f"Todas as {repetitions} repetições falharam no probe {probe.id} (Modo B)",
                context={'judge_label': self.label, 'probe_id': probe.id, 'failures': failures},
            )
        return measurement

    def run(self, probe: GoldenProbe, repetitions: int, modo: str = 'b') -> ProbeMeasurement:
        """Por padrão, toda avaliação usa o Modo B (D-03)."""
        if modo == 'a':
            return self.run_modo_a(probe, repetitions)
        elif modo == 'b':
            return self.run_modo_b(probe, repetitions)
        else:
            raise ValueError(f"Modo desconhecido: {modo}")
