import dspy
import threading
from pathlib import Path
from src.experience_store import ExperienceStore
from src.infrastructure.dspy_impl import AvaliadorModoBSignature
from src.config import get_drift_thresholds
from dspy.teleprompt import BootstrapFewShot
from src.drift.gate import DriftGate
from src.drift.exceptions import DriftMeasurementError
from src.drift.models import DriftReport, DriftThresholds
from src.drift.golden import GoldenSet
from src.drift.runner import JudgeProbeRunner
from src.drift.cache import load_drift_cache, save_drift_cache
from src.drift.metrics import medir_drift

_compile_lock = threading.Lock()

# Status possíveis de compilação (mapeados em routers/jobs.py):
#   "compiled"           — recompilado e validado contra o golden.
#   "no_data"            — sem experiências de alta qualidade.
#   "drift_rejected"     — candidato rejeitado pelo portão (não persistiu).
#   "measurement_error"  — falha ao medir drift com golden presente.
#   "golden_empty_open"  — golden ausente; compilação sem portão (fail-open, EC4).


def _build_trainset(store: ExperienceStore, min_reward: float) -> list:
    melhores = [exp for exp in store.experiences if exp.absolute_reward >= min_reward and exp.instruction and exp.parent_instruction]
    if not melhores:
        return []

    trainset = []
    for exp in melhores:
        exemplo = dspy.Example(
            skill_original=exp.parent_instruction,
            skill_otimizada=exp.instruction,
            regras_adicionais='Preservar todas as regras comportamentais anteriores.'
        ).with_inputs('skill_original', 'skill_otimizada', 'regras_adicionais')
        trainset.append(exemplo)
    return trainset

def _run_teleprompt(trainset: list, candidate_path: Path):
    def trivial_metric(example, pred, trace=None):
        return True

    print("Iniciando compilação (Teleprompting) via BootstrapFewShot...")
    teleprompter = BootstrapFewShot(metric=trivial_metric, max_bootstrapped_demos=3, max_labeled_demos=0)
    avaliador_module = dspy.Predict(AvaliadorModoBSignature)
    compilado = teleprompter.compile(avaliador_module, trainset=trainset)
    compilado.save(str(candidate_path))

def _measure_drift(candidate_path: Path, golden: GoldenSet, repetitions: int, thresholds: DriftThresholds) -> DriftReport:
    """RN-07: Mede o drift do candidato carregado a partir do candidate_path."""
    runner_cand = JudgeProbeRunner("candidato")
    runner_cand.load_candidate(str(candidate_path))
    return medir_drift(runner_cand, golden, repetitions, thresholds)


def _gate_decision(report_cand: DriftReport, report_atual: DriftReport | None, thresholds: DriftThresholds) -> object:
    """Toma a decisão de aprovação/rejeição no DriftGate."""
    return DriftGate.avaliar_candidato(report_cand, report_atual, thresholds)


def _persist_candidate(candidate_path: Path, out_path: Path, output_dir: Path, report_cand: DriftReport) -> None:
    """Persiste o candidato e atualiza o snapshot do cache de drift."""
    if out_path.exists():
        bak_path = output_dir / 'avaliador_modo_b_otimizado.json.bak'
        out_path.replace(bak_path)
    candidate_path.replace(out_path)
    save_drift_cache(report_cand)


def _evaluate_drift_gate(candidate_path: Path, out_path: Path, output_dir: Path) -> str:
    """
    RN-07: Fail-closed em erro de medição
    RN-08: Fail-open se golden vazio
    """
    golden = GoldenSet()
    if golden.is_empty():
        # EC4: fail-open — não trava deploy limpo, mas avisa com destaque máximo.
        candidate_path.replace(out_path)
        print(
            "\n" + "=" * 72 + "\n"
            "⚠  WARNING — PORTÃO DE DRIFT DESATIVADO (EC4: fail-open)\n"
            "   Golden set ausente ou vazio. O candidato foi persistido SEM\n"
            "   validação de drift. Um juiz com desvio comportamental severo\n"
            "   pode estar ativo em produção.\n"
            f"  Arquivo persistido: {out_path}\n"
            "   AÇÃO RECOMENDADA: recrie o golden set e recompile o avaliador.\n"
            + "=" * 72 + "\n"
        )
        return "golden_empty_open"

    cfg = get_drift_thresholds()
    thresholds = DriftThresholds.from_config(cfg)
    repetitions = cfg['repetitions']

    try:
        # Medir candidato (instância DSPy isolada) usando a função extraída.
        report_cand = _measure_drift(candidate_path, golden, repetitions, thresholds)

        # Medir/recuperar juiz atual.
        report_atual = load_drift_cache()
        if report_atual is None:
            runner_atual = JudgeProbeRunner("atual")
            if out_path.exists():
                runner_atual.load_candidate(str(out_path))
            else:
                runner_atual.as_zero()
            try:
                report_atual = medir_drift(runner_atual, golden, repetitions, thresholds)
            except DriftMeasurementError as e:
                print(f"[!] Não foi possível medir o juiz atual ({e.message}); usando floors absolutos.")
                report_atual = None

        decision = _gate_decision(report_cand, report_atual, thresholds)

        if not decision.accept:
            # Veto — NÃO sobrescreve o juiz em produção.
            try:
                candidate_path.unlink()
            except Exception:
                pass
            print(f"[!] PORTÃO REJEITOU candidato: {decision.reason}")
            return "drift_rejected"

        # Aceito — snapshot do anterior, persistência, cache.
        _persist_candidate(candidate_path, out_path, output_dir, report_cand)

        print(f"[*] Modelo avaliador recompilado, validado e salvo em: {out_path}")
        print(f"    Drift do novo juiz: spearman={report_cand.spearman_composite:.3f} offset={report_cand.offset_scale:.2f}")
        return "compiled"

    except DriftMeasurementError as e:
        # Golden presente mas medição falhou → fail-closed (não degrada p/ save cego).
        try:
            candidate_path.unlink()
        except Exception:
            pass
        print(f"[!] Erro de medição de drift ({e.message}). Fail-closed: candidato descartado.")
        return "measurement_error"

def compilar_avaliador(lm=None, min_reward: float = 0.8) -> str:
    """
    Recompila o juiz via BootstrapFewShot e valida o candidato contra o golden
    set antes de persistir (A1 — grounding da recompensa).

    Retorna um status (não mais bool). O save é sob prova (vetor, não otimizador).
    """
    if not _compile_lock.acquire(blocking=False):
        print("[!] Uma compilação do avaliador já está em andamento. Ignorando esta solicitação.")
        return "no_data"

    try:
        if lm:
            dspy.settings.configure(lm=lm)

        store = ExperienceStore()
        trainset = _build_trainset(store, min_reward)
        if not trainset:
            print("Nenhuma experiência de alta qualidade (com instrução) encontrada para compilação.")
            return "no_data"

        print(f"Encontradas {len(trainset)} experiências excelentes para o dataset.")

        output_dir = Path('src/outputs/models')
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / 'avaliador_modo_b_otimizado.json'
        candidate_path = output_dir / 'avaliador_modo_b_otimizado.candidate.json'

        _run_teleprompt(trainset, candidate_path)

        return _evaluate_drift_gate(candidate_path, out_path, output_dir)

    finally:
        _compile_lock.release()


if __name__ == "__main__":
    from src.config import setup
    lm = setup()
    compilar_avaliador(lm=lm)
