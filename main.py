import sys
import argparse
import difflib
from pathlib import Path

from src.config import setup
from src.optimizer import Optimizer
from src.store import save_optimized_skill
from src.infrastructure.events import JobEventEmitter

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

    compile_parser = subparsers.add_parser("compile", help="Compila os agentes usando DSPy Optimizers com memórias passadas")
    
    args = parser.parse_args()
    
    if args.command == "audit":
        skill_file = Path(args.skill_path)
        if not skill_file.exists():
            print(f"[!] Arquivo não encontrado: {skill_file}", file=sys.stderr)
            sys.exit(1)
        
        from src.context_audit import audit_context_heuristics
        skill_text = skill_file.read_text(encoding="utf-8")
        report = audit_context_heuristics(skill_text)
        
        print(f"\n=======================================================")
        print(f"       AUDITORIA DE CONTEXTO: {skill_file.name}")
        print(f"=======================================================")
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


if __name__ == "__main__":
    main()
