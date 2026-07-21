"""
Experiment B — Judge Noise Measurement (REAL LLM)

Mede a variancia do juiz DSPyAvaliadorModoB avaliando a mesma skill fixa
N vezes e calculando desvio-padrao, mediana e histograma das notas.

Uso:
    python tests/experiments/run_real_judge.py --n 20

Output:
    results_exp_b_real.json com raw_scores, mean, stdev, median, min, max
    e recomendacao automatica baseada nos thresholds: 0.05 / 0.10 / 0.20
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

# Adiciona o diretorio raiz ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.signatures import funcao_de_recompensa
from src.infrastructure.container import Container

# ── Mesma skill fixa usada nos experimentos mock (test_variance.py) ──────────

SKILL_BASE = (
    "Voce e um assistente de IA. Siga estas regras:\n"
    "1. Sempre responda em portugues.\n"
    "2. Seja conciso e direto.\n"
    "3. Use formatacao markdown quando apropriado.\n"
    "4. Nunca invente informacoes."
)

FIXED_SKILL_FOR_JUDGE = (
    "## Raciocinio\nPremissas: O usuario precisa de clareza.\n"
    "Deduccoes: Estrutura melhora compreensao.\n"
    "Conclusao: Usar formato estruturado.\n\n"
    "## Regras\n1. Responda sempre em topicos.\n"
    "2. Use exemplos concretos.\n\n"
    "## Conclusao\nAplique o formato acima em todas as respostas."
)


def run_experiment_b_real(n: int = 20) -> dict:
    """Avalia FIXED_SKILL_FOR_JUDGE N vezes com o juiz LLM real.

    Returns:
        dict com raw_scores, mean, stdev, median, min, max, histogram_bins,
        recommendation e threshold usado.
    """
    container = Container()
    avaliador = container.get_avaliador_modo_b()

    raw_scores = []
    errors = []

    print("\n=== Experiment B: Judge Noise (REAL LLM) ===")
    print(f"  N={n}")
    print(f"  Skill: {FIXED_SKILL_FOR_JUDGE[:80]}...")
    print("  Running...")

    for i in range(n):
        try:
            reward, feedback = funcao_de_recompensa(
                avaliador_modo_b=avaliador,
                skill_original=SKILL_BASE,
                skill_otimizada=FIXED_SKILL_FOR_JUDGE,
                regras_adicionais="",
            )
            raw_scores.append(reward)
            print(f"    [{i+1}/{n}] reward={reward:.3f}")
        except Exception as e:
            errors.append({"run": i, "error": str(e)})
            print(f"    [{i+1}/{n}] ERROR: {e}")

    if not raw_scores:
        return {"error": "No successful evaluations", "errors": errors}

    mean = statistics.mean(raw_scores)
    stdev = statistics.stdev(raw_scores) if len(raw_scores) >= 2 else 0.0
    median = statistics.median(raw_scores)
    min_val = min(raw_scores)
    max_val = max(raw_scores)

    # ── Histograma ASCII (10 bins) ──────────────────────────────────────
    bin_count = 10
    bin_width = (max_val - min_val) / bin_count if max_val > min_val else 0.1
    bins = [0] * bin_count
    for s in raw_scores:
        idx = min(bin_count - 1, int((s - min_val) / bin_width))
        bins[idx] += 1

    # ── Recomendacao automatica ─────────────────────────────────────────
    if stdev <= 0.05:
        recommendation = (
            "Juiz estavel (sigma <= 0.05). "
            "Correcoes #3 (buzzword) e #5 (desempate) bastam. "
            "Correcao #2 (mediana) NAO e necessaria."
        )
    elif stdev <= 0.10:
        recommendation = (
            "Ruido moderado (0.05 < sigma <= 0.10). "
            "Recomendo Correcao #2 com MEDIANA DE 3 simulacoes "
            "para raiz e melhor no."
        )
    elif stdev <= 0.20:
        recommendation = (
            "Ruido alto (0.10 < sigma <= 0.20). "
            "Recomendo Correcao #2 com MEDIANA DE 5 simulacoes "
            "para raiz e melhor no."
        )
    else:
        recommendation = (
            "Juiz muito instavel (sigma > 0.20). "
            "Recomendo MEDIANA DE 5 + REVISAO DO PROMPT DO AVALIADOR. "
            "Considere tambem a Correcao #4 (best-so-far checkpoint)."
        )

    result = {
        "skill_original": SKILL_BASE,
        "skill_otimizada": FIXED_SKILL_FOR_JUDGE[:100] + "...",
        "n_evaluations": n,
        "raw_scores": raw_scores,
        "mean": round(mean, 4),
        "stdev": round(stdev, 4),
        "median": round(median, 4),
        "min": round(min_val, 4),
        "max": round(max_val, 4),
        "histogram_bins": {
            f"{min_val + i*bin_width:.2f}-{min_val + (i+1)*bin_width:.2f}": bins[i]
            for i in range(bin_count)
        },
        "errors": errors,
        "thresholds_used": {"stable": 0.05, "moderate": 0.10, "high": 0.20},
        "recommendation": recommendation,
    }

    # ── Output ──────────────────────────────────────────────────────────
    print("\n  Results:")
    print(f"    mean={mean:.3f}, stdev={stdev:.3f}, median={median:.3f}")
    print(f"    min={min_val:.3f}, max={max_val:.3f}")
    print("  Histogram:")
    max_bar = max(bins) if bins else 1
    for i in range(bin_count):
        lo = min_val + i * bin_width
        hi = min_val + (i + 1) * bin_width
        bar = "*" * max(1, int(bins[i] / max_bar * 40))
        print(f"    [{lo:.2f}-{hi:.2f}]: {bar} ({bins[i]})")

    print(f"\n  >>> RECOMMENDATION: {recommendation}")

    output_path = Path("tests/experiments/results_exp_b_real.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Results saved to: {output_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Measure judge LLM noise for variance diagnosis"
    )
    parser.add_argument(
        "--n", type=int, default=20,
        help="Number of evaluations (default: 20, recommended: 20-40)"
    )
    args = parser.parse_args()

    if args.n < 5:
        print("ERROR: --n must be at least 5 for meaningful stdev estimation.")
        sys.exit(1)

    run_experiment_b_real(n=args.n)


if __name__ == "__main__":
    main()