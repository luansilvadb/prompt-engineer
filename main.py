import argparse
import difflib
import re
import sys
import threading
import time as time_mod
from pathlib import Path

from src.config import setup
from src.infrastructure.container import get_container
from src.infrastructure.events import JobEventEmitter
from src.optimizer import Optimizer
from src.store import save_optimized_skill

sys.stdout.reconfigure(encoding='utf-8')


def _load_skill(path_str: str) -> tuple[Path, str]:
    """Valida e carrega o arquivo de skill. Retorna (Path, conteúdo)."""
    skill_file = Path(path_str)
    if not skill_file.exists():
        print(f"[!] Arquivo não encontrado: {skill_file}", file=sys.stderr)
        sys.exit(1)
    return skill_file, skill_file.read_text(encoding="utf-8")


def _build_optimizer(skill_text: str, container, emitter: JobEventEmitter) -> Optimizer:
    return Optimizer(
        skill_original=skill_text,
        config=container.get_config(),
        emitter=emitter,
        strategy_discoverer=container.get_strategy_discoverer(),
        agent=container.get_agent(),
        agent_cognitivo=container.get_agent_cognitivo(),
        avaliador_modo_b=container.get_avaliador_modo_b(),
        experience_store=container.get_experience_store(),
        bandit=container.get_bandit(),
        strategy_registry=container.get_strategy_registry(),
    )


def _display_diff_and_prompt(skill_bruta: str, melhor_instrucao: str, skill_file: Path) -> None:
    """Exibe o diff e interage com o usuário para salvar/descartar."""
    diff = difflib.unified_diff(
        skill_bruta.splitlines(keepends=True),
        melhor_instrucao.splitlines(keepends=True),
        fromfile=f"a/{skill_file.name}", tofile=f"b/{skill_file.name}",
    )
    diff_text = ''.join(diff)
    print("\n>>> DIFF DAS ALTERAÇÕES <<<\n")
    if not diff_text.strip():
        print("Nenhuma alteração foi feita na skill. Ela já está otimizada.")
        return
    print(diff_text)
    resposta = input("\n[?] Deseja aplicar essa otimização no arquivo original? (y/N): ")
    if resposta.strip().lower() in ['y', 'yes', 's', 'sim']:
        skill_file.write_text(melhor_instrucao, encoding="utf-8")
        print(f"[+] Skill atualizada com sucesso em: {skill_file}")
    else:
        print("[-] Otimização descartada pelo usuário.")
    try:
        output_file = save_optimized_skill(melhor_instrucao)
        print(f"[i] Cópia de segurança salva em: '{output_file}'")
    except Exception:
        pass


def _run_audit(skill_file: Path, skill_text: str) -> None:
    from src.context_audit import audit_context_heuristics
    report = audit_context_heuristics(skill_text)
    print("\n=======================================================")
    print(f"       AUDITORIA DE CONTEXTO: {skill_file.name}")
    print("=======================================================")
    print(f"Score Geral: {report.overall_score:.1f}/10  —  Classificação: {report.grade}\n")
    print("CRITÉRIOS DETALHADOS:")
    for c in report.criteria:
        print(f"  • {c.label_pt:<30} [{c.score:.1f}/10]  {c.key_finding}")
    print("\nRISCOS COMPORTAMENTAIS PREVISTOS:")
    for r in report.predicted_risks:
        print(f"  [!] {r}")
    print("\nTOP 3 CORREÇÕES DE MAIOR ALAVANCAGEM:")
    for i, f in enumerate(report.top_fixes, 1):
        print(f"  {i}. {f}")
    print("=======================================================\n")


def _run_check(skill_file: Path, skill_text: str) -> None:
    print(f"[*] Carregando skill de: {skill_file}")
    try:
        setup()
        container = get_container()
        emitter = JobEventEmitter(on_log=print, on_error=lambda msg: print(msg, file=sys.stderr))
        melhor_instrucao = _build_optimizer(skill_text, container, emitter).optimize()
        _display_diff_and_prompt(skill_text, melhor_instrucao, skill_file)
    except Exception as e:
        print(f"\n[!] Erro fatal durante a execução: {e}", file=sys.stderr)
        sys.exit(1)


def _run_watch(skill_file: Path, skill_text: str) -> None:
    print(f"\n{'=' * 60}")
    print("  SKILL OPTIMIZER — Modo Interativo")
    print(f"  Arquivo: {skill_file.name}")
    print(f"{'=' * 60}")

    setup()
    container = get_container()

    state = {
        "iteration": 0, "max_iterations": container.get_config().max_iterations,
        "best_reward": 0.0, "last_reward": 0.0, "node_count": 0,
        "llm_calls": 0, "elapsed": 0.0, "status": "running",
        "latest_log": "", "lock": threading.Lock(), "done": threading.Event(),
    }

    def update_state(msg: str) -> None:
        with state["lock"]:
            state["latest_log"] = msg
            if m := re.search(r"Iteração MCTS (\d+)/(\d+)", msg):
                state["iteration"], state["max_iterations"] = int(m.group(1)), int(m.group(2))
            if m := re.search(r"Recompensa obtida: ([\d.]+)", msg):
                r = float(m.group(1))
                state["last_reward"] = r
                if r > state["best_reward"]:
                    state["best_reward"] = r
            if m := re.search(r"(\d+) nós únicos", msg):
                state["node_count"] = int(m.group(1))
            if m := re.search(r"(\d+) chamadas LLM", msg):
                state["llm_calls"] += int(m.group(1))
            if "OTIMIZAÇÃO CONCLUÍDA" in msg:
                state["status"] = "completed"
            elif "INTERROMPIDA" in msg:
                state["status"] = "cancelled"

    emitter = JobEventEmitter(on_log=update_state, on_error=update_state)
    result_holder: dict = {"instruction": None, "error": None}

    def run_optimization() -> None:
        try:
            optimizer = _build_optimizer(skill_text, container, emitter)
            result_holder["instruction"] = optimizer.optimize()
        except Exception as e:
            result_holder["error"] = str(e)
        finally:
            state["done"].set()

    opt_thread = threading.Thread(target=run_optimization, daemon=True)
    start_time = time_mod.time()
    opt_thread.start()

    # Dashboard loop
    try:
        while not state["done"].is_set():
            with state["lock"]:
                it, total = state["iteration"], state["max_iterations"]
                best, last = state["best_reward"], state["last_reward"]
                nodes, calls = state["node_count"], state["llm_calls"]
                elapsed = time_mod.time() - start_time

            _render_dashboard(skill_file.name, it, total, best, last, nodes, calls, elapsed,
                              state.get("latest_log", ""))
            time_mod.sleep(1.0)
    except KeyboardInterrupt:
        sys.stdout.write("\n\n[!] Interrompendo otimização...\n")
        state["done"].set()

    opt_thread.join()

    if result_holder["error"]:
        print(f"\n[!] Erro: {result_holder['error']}", file=sys.stderr)
        sys.exit(1)

    if melhor := result_holder["instruction"]:
        _display_diff_and_prompt(skill_text, melhor, skill_file)


def _render_dashboard(skill_name: str, it: int, total: int, best: float, last: float,
                      nodes: int, calls: int, elapsed: float, latest_log: str) -> None:
    """Renderiza o dashboard interativo no terminal."""
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.write(f"  SKILL OPTIMIZER — {skill_name}\n")
    sys.stdout.write(f"  {'=' * 56}\n\n")
    pct = min(100, int((it / max(1, total)) * 100))
    bar = "█" * int(40 * pct / 100) + "░" * (40 - int(40 * pct / 100))
    sys.stdout.write(f"  Iteração:  [{bar}] {pct}%  ({it}/{total})\n\n")
    sys.stdout.write(f"  Melhor Recompensa:  {best:.3f}\n")
    sys.stdout.write(f"  Última Recompensa:  {last:.3f}\n")
    sys.stdout.write(f"  Nós na Árvore:      {nodes}\n")
    sys.stdout.write(f"  Chamadas LLM:       {calls}\n")
    sys.stdout.write(f"  Tempo Decorrido:    {elapsed:.0f}s\n")
    if latest_log:
        sys.stdout.write(f"\n  ── Último evento ──\n  {latest_log[-120:]}\n")
    sys.stdout.write(f"\n  {'─' * 56}\n  Pressione Ctrl+C para interromper\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Otimizador de Skills CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in [("check", "Audita e otimiza uma skill via MCTS RL"),
                             ("audit", "Audita o contexto de uma skill nos 7 critérios empíricos"),
                             ("compile", "Compila os agentes usando DSPy Optimizers com memórias passadas"),
                             ("watch", "Otimiza uma skill com dashboard interativo no terminal")]:
        subparsers.add_parser(name, help=help_text).add_argument("skill_path", type=str, nargs="?" if name == "compile" else None, help="Caminho para o arquivo da skill (.md)")

    args = parser.parse_args()

    if args.command == "compile":
        from scripts.compile_dspy import compile_agents
        compile_agents()
        return

    skill_file, skill_text = _load_skill(args.skill_path)

    handlers = {
        "audit": lambda: _run_audit(skill_file, skill_text),
        "check": lambda: _run_check(skill_file, skill_text),
        "watch": lambda: _run_watch(skill_file, skill_text),
    }
    handlers[args.command]()


if __name__ == "__main__":
    main()
