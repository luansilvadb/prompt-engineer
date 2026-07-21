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
#   "golden_required"    — golden ausente; candidato DESCARTADO (fail-closed). Juiz anterior preservado.


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

def _run_teleprompt(trainset: list, candidate_path: Path, optimizer_type: str = "bootstrap"):
    def quality_metric(example, pred, trace=None):
        if not pred:
            return False
        # Suporta tanto objetos quanto dicionários (flexibilidade DSPy 3.x)
        manteve = getattr(pred, 'manteve_regras_criticas', None)
        if manteve is None and isinstance(pred, dict):
            manteve = pred.get('manteve_regras_criticas', False)
        if isinstance(manteve, str):
            manteve = manteve.lower() in ('true', '1', 'sim')
        if not manteve:
            return False

        # Penalizar candidatos com defeitos críticos estruturais ou contradições
        defeitos = getattr(pred, 'defeitos_encontrados', None)
        if defeitos is None and isinstance(pred, dict):
            defeitos = pred.get('defeitos_encontrados', [])
        if defeitos and len(defeitos) > 3:
            return False

        feedback = getattr(pred, 'feedback_detalhado', '')
        if not feedback and isinstance(pred, dict):
            feedback = pred.get('feedback_detalhado', '')
        if not feedback or len(str(feedback).strip()) < 5:
            return False

        nota = getattr(pred, 'nota_qualidade', None)
        if nota is None and isinstance(pred, dict):
            nota = pred.get('nota_qualidade', None)
        if nota is not None:
            try:
                val = float(nota)
                if val < 0.0:
                    return False
            except (ValueError, TypeError):
                pass

        return True

    avaliador_module = dspy.Predict(AvaliadorModoBSignature)

    if optimizer_type and optimizer_type.lower() == "gepa":
        try:
            from dspy.teleprompt import GEPA
            print("Iniciando compilação (Teleprompting) via GEPA...")
            teleprompter = GEPA(metric=quality_metric, auto="light")
            compilado = teleprompter.compile(avaliador_module, trainset=trainset)
            compilado.save(str(candidate_path))
            return
        except Exception as e:
            print(f"[!] Fallback para BootstrapFewShot devido a erro ou indisponibilidade em GEPA: {e}")

    if optimizer_type and optimizer_type.lower() in ("mipro", "miprov2"):
        try:
            from dspy.teleprompt import MIPROv2
            print("Iniciando compilação (Teleprompting) via MIPROv2...")
            teleprompter = MIPROv2(metric=quality_metric, auto="light")
            compilado = teleprompter.compile(avaliador_module, trainset=trainset)
            compilado.save(str(candidate_path))
            return
        except Exception as e:
            print(f"[!] Fallback para BootstrapFewShot devido a erro ou indisponibilidade em MIPROv2: {e}")

    if optimizer_type and optimizer_type.lower() in ("bootstrap_rs", "bootstrapfewshotwithrandomsearch", "random_search"):
        try:
            from dspy.teleprompt import BootstrapFewShotWithRandomSearch
            print("Iniciando compilação (Teleprompting) via BootstrapFewShotWithRandomSearch...")
            teleprompter = BootstrapFewShotWithRandomSearch(
                metric=quality_metric,
                max_bootstrapped_demos=3,
                max_labeled_demos=0,
                num_candidate_sets=4,
            )
            compilado = teleprompter.compile(avaliador_module, trainset=trainset)
            compilado.save(str(candidate_path))
            return
        except Exception as e:
            print(f"[!] Fallback para BootstrapFewShot devido a erro ou indisponibilidade em BootstrapFewShotWithRandomSearch: {e}")

    print("Iniciando compilação (Teleprompting) via BootstrapFewShot...")
    teleprompter = BootstrapFewShot(metric=quality_metric, max_bootstrapped_demos=3, max_labeled_demos=0)
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
    RN-08 (revertido): Fail-CLOSED se golden vazio.

    Razão: fail-open permitia persitir um juíz treinado com dados sintéticos
    sem validação, criando um ciclo vicioso de model collapse:
      ExperienceStore (sintético) → treina Juíz → Juíz viesado pontua
      novas skills → mais dados sintéticos viesados → loop fechado.
    Fail-closed interrompe o ciclo: sem golden set, sem novo juíz.
    """
    golden = GoldenSet()
    if golden.is_empty():
        # Fail-closed: descarta candidato e preserva juíz atual.
        try:
            candidate_path.unlink(missing_ok=True)
        except Exception:
            pass
        print(
            "\n" + "=" * 72 + "\n"
            "❌ PORTÃO DE DRIFT: CANDIDATO DESCARTADO (fail-closed)\n"
            "   Golden set ausente ou vazio. O candidato NÃO foi persistido.\n"
            "   Juíz anterior preservado para evitar model collapse.\n"
            "   AÇÃO NECESSÁRIA: crie o golden set antes de treinar o avaliador.\n"
            "   Use: POST /api/generate-golden ou edite manualmente\n"
            "   src/outputs/golden/golden_set.json\n"
            + "=" * 72 + "\n"
        )
        return "golden_required"

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

def compilar_avaliador(lm=None, min_reward: float = 0.8, optimizer_type: str = "bootstrap") -> str:
    """
    Recompila o juiz via BootstrapFewShot ou MIPROv2 e valida o candidato contra o golden
    set antes de persistir (A1 — grounding da recompensa).

    Retorna um status (não mais bool). O save é sob prova (vetor, não otimizador).
    """
    if not _compile_lock.acquire(blocking=False):
        print("[!] Uma compilação do avaliador já está em andamento. Ignorando esta solicitação.")
        return "no_data"

    try:
        # Nota: dspy.configure() já foi chamado pelo setup() na thread do event loop.
        # NÃO chamamos dspy.settings.configure() aqui — seria bloqueado pelo dspy
        # por tentar reconfigurar o singleton a partir de uma thread worker diferente.
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

        _run_teleprompt(trainset, candidate_path, optimizer_type=optimizer_type)

        return _evaluate_drift_gate(candidate_path, out_path, output_dir)

    finally:
        _compile_lock.release()


if __name__ == "__main__":
    from src.config import setup
    lm = setup()
    compilar_avaliador(lm=lm)
