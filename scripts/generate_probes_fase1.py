"""
Fase 1: Script auxiliar para gerar candidatos a probes via LLM.
Cada categoria usa um template diferente, inspirado no LLMBar.
Os candidatos gerados precisam de auditoria humana antes de entrar no golden set.
"""
import sys
import json
sys.path.insert(0, '.')

import dspy
from src.config import setup


# ── Templates por categoria ──────────────────────────────

# A. NATURAL: pares reais do dominio (debug, codigo, sistema)
NATURAL_CANDIDATES = [
    {
        "id": "NAT-1",
        "category": "natural",
        "instruction": "Escreva uma funcao em Python que recebe uma lista e retorna apenas os numeros pares.",
        "skill_original": "# Python helper\n# Write functions as requested.",
        "skill_otimizada": "def filter_even(numbers):\n    return [n for n in numbers if n % 2 == 0]",
        "output_bom": "def filter_even(numbers):\n    \"\"\"Return only even numbers from a list.\"\"\"\n    return [n for n in numbers if n % 2 == 0]\n\n# Example:\n# filter_even([1, 2, 3, 4]) => [2, 4]",
        "output_ruim": "Here's a great solution for filtering numbers! I've written a comprehensive function that handles multiple cases:\n\ndef process_numbers(data):\n    results = []\n    for item in data:\n        # Check if the number meets our criteria\n        if isinstance(item, int) and item > 0:\n            results.append(item)\n    # Also include negative numbers that are even\n    for item in data:\n        if isinstance(item, int) and item < 0 and abs(item) % 2 == 0:\n            results.append(item)\n    return sorted(results)\n\nThis function is more robust because it validates types and handles both positive and negative numbers!",
        "expected_manteve_regras_criticas": True,
        "rank_band": "alto",
        "verifier": "Output bom retorna apenas pares. Output ruim filtra positivos primeiro e inclui negativos pares separadamente, alem de ordenar — nao segue a instrucao simples."
    },
]

# B. NEIGHBOR: instrucao similar, output errado
NEIGHBOR_TEMPLATE = """
Generate a new instruction that is highly relevant to but different from the given instruction.
The new instruction should ask for something DIFFERENT enough that a correct answer to the new
instruction would be WRONG for the original instruction.

Given instruction: {instruction}

Return ONLY the new instruction text, nothing else.
"""

# C. GPTOUT: output incorreto mas bem escrito
GPTOUT_TEMPLATE = """
Given the following instruction, generate an output that FAILS to follow it correctly,
but LOOKS like a good, well-written response. The output should:
1. Superficially resemble a correct response
2. Actually be wrong, incomplete, or miss the point
3. Be well-formatted and polished

Instruction: {instruction}

Generate ONLY the incorrect output, no explanation.
"""

# D. MANUAL: construidos diretamente (sem LLM)
MANUAL_CANDIDATES = [
    {
        "id": "MAN-1",
        "category": "manual",
        "instruction": "Liste 3 causas comuns de erros de compilacao em C++.",
        "skill_original": "# Code review assistant\n# Help identify issues.",
        "skill_otimizada": "1. Missing semicolons\n2. Undeclared variables\n3. Type mismatches",
        "output_bom": "1. Faltam ponto-e-virgula (;)\n2. Variaveis nao declaradas\n3. Incompatibilidade de tipos",
        "output_ruim": "Compilation errors in C++ stem from several architectural and semantic issues. First, syntactic violations — the compiler's parser expects a specific grammar, and even minor deviations cascade into cascading errors. Second, the linker phase can fail due to unresolved external symbols, often from missing header includes. Third, template instantiation failures produce notoriously cryptic error messages. Fourth, memory model violations... [continua com 7 causas em prosa eloquente, mas a instrucao pedia exatamente 3 em formato de lista]",
        "expected_manteve_regras_criticas": True,
        "rank_band": "alto",
        "verifier": "Instrucao pede 3 itens em formato de lista. Output bom entrega exatamente 3 em lista. Output ruim entrega 4+ em prosa."
    },
]

# E. CONSTRAINT: restricoes lexicais
CONSTRAINT_CANDIDATES = [
    {
        "id": "CON-1",
        "category": "constraint",
        "instruction": "Explique o que e um deadlock em no maximo 2 frases. Responda exatamente em 2 frases, nem mais nem menos.",
        "skill_original": "# Technical explainer\n# Be concise.",
        "skill_otimizada": "Deadlock ocorre quando dois ou mais processos ficam bloqueados permanentemente, cada um esperando por um recurso que o outro detem. E uma situacao de impasse que impede o progresso de todos os processos envolvidos.",
        "output_bom": "Deadlock ocorre quando dois ou mais processos ficam bloqueados permanentemente, cada um esperando por um recurso que o outro detem. E uma situacao de impasse que impede o progresso de todos os processos envolvidos.",
        "output_ruim": "A deadlock is a critical condition in concurrent computing where processes enter a circular waiting state. It's one of the most challenging problems in operating systems design. The four necessary conditions for deadlock are: mutual exclusion, hold and wait, no preemption, and circular wait. Understanding these conditions is essential for any systems programmer.",
        "expected_manteve_regras_criticas": True,
        "rank_band": "alto",
        "verifier": "Restricao: exatamente 2 frases. Output bom tem 2 frases. Output ruim tem 4 frases."
    },
]

# F. NEGATION: instrucoes com negacao
NEGATION_CANDIDATES = [
    {
        "id": "NEG-1",
        "category": "negation",
        "instruction": "Me diga o que NAO fazer ao debugar um erro de conexao com banco de dados.",
        "skill_original": "# Database debugging\n# Provide guidance.",
        "skill_otimizada": "NAO faca: \n1. Alterar credenciais sem verificar se o servico esta rodando\n2. Reiniciar o servidor de producao durante horario de pico\n3. Ignorar mensagens de timeout e assumir que e problema de firewall",
        "output_bom": "NAO faca: \n1. Alterar credenciais sem verificar se o servico esta rodando\n2. Reiniciar o servidor de producao durante horario de pico\n3. Ignorar mensagens de timeout e assumir que e problema de firewall",
        "output_ruim": "Para debugar erros de conexao com banco de dados, voce DEVE:\n1. Verificar se o servico do banco esta rodando\n2. Confirmar credenciais de acesso\n3. Testar conectividade de rede com ping/telnet\n4. Verificar logs do banco para mensagens de erro",
        "expected_manteve_regras_criticas": True,
        "rank_band": "alto",
        "verifier": "Instrucao pede o que NAO fazer. Output bom lista o que NAO fazer. Output ruim lista o que DEVE fazer (ignorou a negacao)."
    },
]


def main():
    print("=" * 70)
    print("GERADOR DE CANDIDATOS A PROBES — FASE 1 (Golden Set Expandido)")
    print("=" * 70)
    print()
    print("Este script gera candidatos. Auditoria humana e OBRIGATORIA")
    print("antes de inserir no golden_set.json.")
    print()
    print("Checklist de auditoria para cada probe:")
    print("  1. [ ] Instrucao e clara e nao-ambigua?")
    print("  2. [ ] Existe OBJETIVAMENTE um output melhor em instruction following?")
    print("  3. [ ] O output 'ruim' e plausivel (avaliador razoavel poderia se enganar)?")
    print("  4. [ ] O output 'bom' de fato segue a instrucao?")
    print("  5. [ ] O par nao esta contaminado por outro vies (ex: comprimento)?")
    print("  6. [ ] As notas 'expected' sao aproximacoes razoaveis (alpha)?")
    print("  7. [ ] O gerador do par e um modelo DIFERENTE do juiz sendo avaliado?")
    print("  8. [ ] Golden set e single-curator (Luan). Inter-rater reliability nao medida.")
    print()
    print(f"Candidatos pre-definidos: {len(NATURAL_CANDIDATES) + len(MANUAL_CANDIDATES) + len(CONSTRAINT_CANDIDATES) + len(NEGATION_CANDIDATES)}")
    print(f"  NATURAL:    {len(NATURAL_CANDIDATES)}")
    print(f"  MANUAL:     {len(MANUAL_CANDIDATES)}")
    print(f"  CONSTRAINT: {len(CONSTRAINT_CANDIDATES)}")
    print(f"  NEGATION:   {len(NEGATION_CANDIDATES)}")
    print()
    print("Para gerar mais candidatos via LLM (NEIGHBOR, GPTOUT),")
    print("use as funcoes generate_neighbor() e generate_gptout() neste script.")
    print()

    # Mostrar um candidato como exemplo
    print("--- Exemplo de candidato NAT-1 ---")
    print(json.dumps(NATURAL_CANDIDATES[0], indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()