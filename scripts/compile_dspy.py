from pathlib import Path
import dspy
from src.config import setup
from src.infrastructure.container import Container
from src.infrastructure.dspy_impl import DSPyMutadorCognitivoAgent

def create_real_metric(container: Container):
    """
    Cria uma métrica real baseada no AvaliadorModoB (LLM as a Judge).
    Esta métrica avalia o output do mutador contra a instrução original.
    """
    judge = container.get_avaliador_modo_b()
    
    def metric(example, pred, trace=None):
        # Penaliza severamente instruções idênticas
        if example.instrucao_anterior.strip() == pred.nova_instrucao.strip():
            return 0.0
            
        try:
            # Chama o juiz Modo B para avaliar a nova_instrucao gerada
            res = judge(
                skill_original=example.instrucao_anterior,
                skill_otimizada=pred.nova_instrucao,
                regras_adicionais="Avaliação rigorosa durante compilação DSPy."
            )
            
            # Penaliza violação de regras críticas
            if not res.manteve_regras_criticas:
                return 0.0
                
            # Calcula o score normalizado
            score = (
                res.nota_clareza + 
                res.nota_formatacao + 
                res.nota_robustez + 
                res.nota_densidade_informacional + 
                res.nota_acionabilidade + 
                res.nota_anti_fragilidade
            ) / 600.0
            
            return score
        except Exception as e:
            print(f"[!] Erro na métrica durante a compilação: {e}")
            return 0.0
            
    return metric

def compile_agents():
    print("[*] Iniciando compilação avançada (Teleprompter) dos Agentes Cognitivos...")
    setup()
    container = Container()
    
    store = container.get_experience_store()
    experiences = store.experiences
    
    if not experiences:
        print("[-] Nenhuma experiência salva no banco. Execute `main.py check` numa skill primeiro para gerar dados.")
        return
        
    print(f"[*] Total de experiências encontradas: {len(experiences)}")
    
    good_exps = [exp for exp in experiences if exp.delta_reward > 0.05]
    if len(good_exps) < 3:
        print(f"[-] Experiências de sucesso insuficientes ({len(good_exps)}). Precisamos de pelo menos 3.")
        return
        
    print(f"[*] Experiências de sucesso utilizadas para few-shot/search: {len(good_exps)}")
    
    trainset = []
    for exp in good_exps:
        ex = dspy.Example(
            instrucao_anterior=exp.parent_instruction,
            nota_anterior=str(exp.absolute_reward - exp.delta_reward),
            feedback_juiz=exp.feedback,
            estrategia_mutacao=exp.mutation_strategy,
            critica="[Exemplo Otimizado Extraído da Memória]",
            nova_instrucao=exp.instruction
        ).with_inputs('instrucao_anterior', 'nota_anterior', 'feedback_juiz', 'estrategia_mutacao')
        trainset.append(ex)
        
    print("[*] Compilando DSPyMutadorCognitivoAgent com BootstrapFewShotWithRandomSearch...")
    
    agent = DSPyMutadorCognitivoAgent()
    
    # Substituindo BootstrapFewShot (que usava dummy_metric) por BootstrapFewShotWithRandomSearch com métrica real
    from dspy.teleprompt import BootstrapFewShotWithRandomSearch
    
    teleprompter = BootstrapFewShotWithRandomSearch(
        metric=create_real_metric(container),
        max_bootstrapped_demos=2,
        max_labeled_demos=3,
        num_candidate_programs=3,
        num_threads=2
    )
    
    try:
        compiled_predictor = teleprompter.compile(agent._predictor, trainset=trainset)
        
        output_dir = Path('src/outputs/models')
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / 'mutador_cognitivo_otimizado.json'
        
        compiled_predictor.save(str(out_path))
        print(f"[+] Modelo compilado e validado por Métrica LLM salvo em: {out_path}")
        
    except Exception as e:
        print(f"[!] Erro ao compilar agente cognitivo: {e}")
        
    print("\n[+] Compilação finalizada.")
    print("DICA: O agente cognitivo agora usa demonstrações otimizadas (few-shot) descobertas por métrica semântica.")

if __name__ == '__main__':
    compile_agents()

