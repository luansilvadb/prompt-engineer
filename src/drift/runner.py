from src.signatures import Avaliacao
from src.domain.agent_interfaces import JudgeRegistry
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import ProbeMeasurement, GoldenProbe

class JudgeProbeRunner:
    """
    Mede um juiz específico contra probes. Instancia seu PRÓPRIO
    juiz (Modo A / Modo B) obtido do JudgeRegistry, desacoplado
    da infraestrutura concreta (Norma 3).
    """

    def __init__(self, label: str):
        self.label = label
        self._judge = JudgeRegistry.create_judge()
        self._judge_modo_b = JudgeRegistry.create_judge_modo_b()

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
        self._judge.as_zero()

    def as_zero_modo_b(self) -> None:
        """Juiz zerado (sem few-shot) — baseline de drift-zero garantida por construção (Modo B)."""
        self._judge_modo_b.as_zero()

    def run_modo_a(self, probe: GoldenProbe, repetitions: int) -> ProbeMeasurement:
        measurement = ProbeMeasurement(probe_id=probe.id)
        failures = 0
        for _ in range(repetitions):
            try:
                regras = probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.'
                avaliacao = self._judge(
                    skill_original=probe.skill_original,
                    skill_otimizada=probe.skill_otimizada,
                    regras_adicionais=regras
                )
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
                regras = probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.'
                avaliacao = self._judge_modo_b(
                    skill_original=probe.skill_original,
                    skill_otimizada=probe.skill_otimizada,
                    regras_adicionais=regras
                )
                measurement.samples.append(avaliacao)
            except Exception as e:
                import traceback
                print(f"[!] Erro no DSPy (Modo B): {e}")
                traceback.print_exc()
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
