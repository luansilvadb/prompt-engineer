import os
import dspy
from src.config import setup
from src.dspy_signatures import StrategyDiscoverer
from src.mutations import registry

def main():
    setup()
    discoverer = dspy.Predict(StrategyDiscoverer)
    
    # Test strategy discovery
    print("[*] Invocando StrategyDiscoverer...")
    nova_estrat = discoverer(
        skill_atual="Esta é uma instrução simples que precisa ser melhorada.",
        feedbacks_recentes="O agente ignora as instruções e produz respostas vagas. Falta foco.",
        estrategias_conhecidas="Nenhuma. Tabula Rasa."
    )
    
    print(f"\n[+] ESTRATÉGIA DESCOBERTA:")
    print(f"Nome: {nova_estrat.nome_estrategia}")
    print(f"Prompt: {nova_estrat.prompt_estrategia}")

if __name__ == "__main__":
    main()
