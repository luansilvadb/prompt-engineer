import json
from pathlib import Path

def main():
    path = Path('src/outputs/experiences/experience_log.jsonl')
    if not path.exists():
        print("Nenhuma experiência encontrada.")
        return
        
    lines = path.read_text(encoding='utf-8').strip().split('\n')
    print(f"Total de avaliações do juiz no log: {len(lines)}")
    
    rewards = []
    for line in lines:
        if not line: continue
        data = json.loads(line)
        rewards.append(data.get('absolute_reward', 0.0))
        
    if rewards:
        avg = sum(rewards) / len(rewards)
        print(f"Média das notas dadas pelo juiz: {avg:.2f}")
        print(f"Nota máxima dada: {max(rewards):.2f}")
        print(f"Nota mínima dada: {min(rewards):.2f}")
        
    print("\n--- Últimas 3 avaliações (Feedback) ---")
    for line in lines[-3:]:
        if not line: continue
        data = json.loads(line)
        r = data.get('absolute_reward', 0.0)
        f = data.get('feedback', '')
        strat = data.get('mutation_strategy', '')
        print(f"[{strat}] Reward: {r:.2f}\nFeedback: {f[:200]}...\n")

if __name__ == "__main__":
    main()
