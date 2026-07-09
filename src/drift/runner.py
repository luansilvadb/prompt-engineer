import dspy
from src.signatures import AvaliadorDeSkill, Avaliacao, _invoke_judge_with
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
