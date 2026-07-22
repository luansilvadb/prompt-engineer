import argparse
import difflib
import sys
from pathlib import Path

from src.config import setup
from src.infrastructure.events import JobEventEmitter
from src.optimizer import Optimizer
from src.store import save_optimized_skill

# Força o terminal do Windows a aceitar caracteres Unicode (ex: '→')
sys.stdout.reconfigure(encoding='utf-8')

def diff_strings(old_text, new_text, filename):
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}"
    )
    return ''.join(diff)

def main():
    parser = argparse.ArgumentParser(description="Otimizador de Skills CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Audita e otimiza uma skill via MCTS RL")
    check_parser.add_argument("skill_path", type=str, help="Caminho para o arquivo da skill (.md)")

    audit_parser = subparsers.add_parser("audit", help="Audita o contexto de uma skill nos 7 critérios empíricos")
    audit_parser.add_argument("skill_path", type=str, help="Caminho para o arquivo da skill (.md)")

    _compile_parser = subparsers.add_parser("compile", help="Compila os agentes usando DSPy Optimizers com memórias passadas")

    watch_parser = subparsers.add_parser("watch", help="Otimiza uma skill com dashboard interativo no terminal")
    watch_parser.add_argument("skill_path", type=str, help="Caminho para o arquivo da skill (.md)")

    args = parser.parse_args()

    if args.command == "audit":
        skill_file = Path(args.skill_path)
        if not skill_file.exists():
            print(f"[!] Arquivo não encontrado: {skill_file}", file=sys.stderr)
            sys.exit(1)

        from src.context_audit import audit_context_heuristics
        skill_text = skill_file.read_text(encoding="utf-8")
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

    elif args.command == "check":
        skill_file = Path(args.skill_path)
        if not skill_file.exists():
            print(f"[!] Arquivo não encontrado: {skill_file}", file=sys.stderr)
            sys.exit(1)

        print(f"[*] Carregando skill de: {skill_file}")
        skill_bruta = skill_file.read_text(encoding="utf-8")

        try:
            setup()
            from src.infrastructure.container import Container
            container = Container()

            emitter = JobEventEmitter(
                on_log=print,
                on_error=lambda msg: print(msg, file=sys.stderr),
            )

            optimizer = Optimizer(
                skill_original=skill_bruta,
                config=container.get_config(),
                emitter=emitter,
                strategy_discoverer=container.get_strategy_discoverer(),
                agent=container.get_agent(),
                agent_cognitivo=container.get_agent_cognitivo(),
                avaliador_modo_b=container.get_avaliador_modo_b(),
                experience_store=container.get_experience_store(),
                bandit=container.create_bandit(),
                strategy_registry=container.create_strategy_registry(),
            )

            melhor_instrucao = optimizer.optimize()

            print("\n>>> DIFF DAS ALTERAÇÕES <<<\n")
            diff = diff_strings(skill_bruta, melhor_instrucao, skill_file.name)
            if not diff.strip():
                print("Nenhuma alteração foi feita na skill. Ela já está otimizada.")
            else:
                print(diff)

                resposta = input("\n[?] Deseja aplicar essa otimização no arquivo original? (y/N): ")
                if resposta.strip().lower() in ['y', 'yes', 's', 'sim']:
                    skill_file.write_text(melhor_instrucao, encoding="utf-8")
                    print(f"[+] Skill atualizada com sucesso em: {skill_file}")
                else:
                    print("[-] Otimização descartada pelo usuário.")

                # Sempre salvar uma cópia por segurança
                try:
                    output_file = save_optimized_skill(melhor_instrucao)
                    print(f"[i] Cópia de segurança salva em: '{output_file}'")
                except Exception:
                    pass

        except Exception as e:
            print(f"\n[!] Erro fatal durante a execução: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "compile":
        from scripts.compile_dspy import compile_agents
        compile_agents()

    elif args.command == "watch":
        skill_file = Path(args.skill_path)
        if not skill_file.exists():
            print(f"[!] Arquivo não encontrado: {skill_file}", file=sys.stderr)
            sys.exit(1)

        skill_bruta = skill_file.read_text(encoding="utf-8")
        print(f"\n{'=' * 60}")
        print("  SKILL OPTIMIZER — Modo Interativo")
        print(f"  Arquivo: {skill_file.name}")
        print(f"{'=' * 60}")

        import re
        import threading
        import time as time_mod

        setup()
        from src.infrastructure.container import Container
        container = Container()

        # Estado compartilhado entre threads
        state = {
            "iteration": 0,
            "max_iterations": container.get_config().max_iterations,
            "best_reward": 0.0,
            "last_reward": 0.0,
            "node_count": 0,
            "llm_calls": 0,
            "elapsed": 0.0,
            "status": "running",
            "strategy_stats": {},
            "latest_log": "",
            "lock": threading.Lock(),
            "done": threading.Event(),
        }

        def update_state(msg: str):
            """Atualiza estado a partir de mensagens de log."""
            with state["lock"]:
                state["latest_log"] = msg

                # Parsing de iteração
                m = re.search(r"Iteração MCTS (\d+)/(\d+)", msg)
                if m:
                    state["iteration"] = int(m.group(1))
                    state["max_iterations"] = int(m.group(2))

                # Parsing de recompensa
                m = re.search(r"Recompensa obtida: ([\d.]+)", msg)
                if m:
                    state["last_reward"] = float(m.group(1))
                    if state["last_reward"] > state["best_reward"]:
                        state["best_reward"] = state["last_reward"]

                # Parsing de nós
                if "nós únicos" in msg:
                    m = re.search(r"(\d+) nós únicos", msg)
                    if m:
                        state["node_count"] = int(m.group(1))

                # Parsing de chamadas LLM
                m = re.search(r"(\d+) chamadas LLM", msg)
                if m:
                    state["llm_calls"] += int(m.group(1))

                # Status final
                if "OTIMIZAÇÃO CONCLUÍDA" in msg:
                    state["status"] = "completed"
                elif "INTERROMPIDA" in msg:
                    state["status"] = "cancelled"

        emitter = JobEventEmitter(
            on_log=lambda msg: update_state(msg),
            on_error=lambda msg: update_state(msg),
        )

        # Executa otimização em thread separada
        result_holder = {"instruction": None, "error": None}

        def run_optimization():
            try:
                optimizer = Optimizer(
                    skill_original=skill_bruta,
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
                    it = state["iteration"]
                    total = state["max_iterations"]
                    best = state["best_reward"]
                    last = state["last_reward"]
                    nodes = state["node_count"]
                    calls = state["llm_calls"]
                    elapsed = time_mod.time() - start_time

                # Limpa tela (ANSI)
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write(f"  SKILL OPTIMIZER — {skill_file.name}\n")
                sys.stdout.write(f"  {'=' * 56}\n\n")

                # Barra de progresso
                pct = min(100, int((it / max(1, total)) * 100))
                bar_width = 40
                filled = int(bar_width * pct / 100)
                bar = "█" * filled + "░" * (bar_width - filled)
                sys.stdout.write(f"  Iteração:  [{bar}] {pct}%  ({it}/{total})\n\n")

                # Métricas
                sys.stdout.write(f"  Melhor Recompensa:  {best:.3f}\n")
                sys.stdout.write(f"  Última Recompensa:  {last:.3f}\n")
                sys.stdout.write(f"  Nós na Árvore:      {nodes}\n")
                sys.stdout.write(f"  Chamadas LLM:       {calls}\n")
                sys.stdout.write(f"  Tempo Decorrido:    {elapsed:.0f}s\n")

                # Último log (truncado)
                latest = state.get("latest_log", "")[-120:]
                if latest:
                    sys.stdout.write("\n  ── Último evento ──\n")
                    sys.stdout.write(f"  {latest[:120]}\n")

                sys.stdout.write(f"\n  {'─' * 56}\n")
                sys.stdout.write("  Pressione Ctrl+C para interromper\n")
                sys.stdout.flush()

                time_mod.sleep(1.0)

        except KeyboardInterrupt:
            sys.stdout.write("\n\n[!] Interrompendo otimização...\n")
            state["done"].set()

        opt_thread.join()

        # Resultado final
        if result_holder["error"]:
            print(f"\n[!] Erro: {result_holder['error']}", file=sys.stderr)
            sys.exit(1)

        melhor_instrucao = result_holder["instruction"]
        if melhor_instrucao:
            print("\n>>> DIFF DAS ALTERAÇÕES <<<\n")
            diff = diff_strings(skill_bruta, melhor_instrucao, skill_file.name)
            if not diff.strip():
                print("Nenhuma alteração foi feita na skill. Ela já está otimizada.")
            else:
                print(diff)
                resposta = input("\n[?] Deseja aplicar essa otimização no arquivo original? (y/N): ")
                if resposta.strip().lower() in ["y", "yes", "s", "sim"]:
                    skill_file.write_text(melhor_instrucao, encoding="utf-8")
                    print(f"[+] Skill atualizada com sucesso em: {skill_file}")
                else:
                    print("[-] Otimização descartada pelo usuário.")

                try:
                    output_file = save_optimized_skill(melhor_instrucao)
                    print(f"[i] Cópia de segurança salva em: '{output_file}'")
                except Exception:
                    pass


if __name__ == "__main__":
    main()
