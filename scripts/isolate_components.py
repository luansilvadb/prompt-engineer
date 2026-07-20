"""
Passo 1: Isolamento de componentes — medir style_gap em 3 configuracoes.

Configuracoes:
  (a) Baseline: juiz zero-shot SEM Rules, SEM Metrics, SEM Swap
  (b) Rules only: juiz com Rules na docstring (o que esta em producao agora)
  (c) Rules+Metrics+Swap: EnhancedJudge completo

7 probes x 5 repeticoes x 3 configuracoes = 105 chamadas.
style_gap = composite(SD-1) - composite(SD-3) — usa APENAS o par SD-1/SD-3.
Os outros 5 probes alimentam metricas de calibracao geral.

Criterio "≈" (epsilon): |gap_b - gap_c| < 0.05 = Metrics neutro para style_gap
(Definido a priori, antes de ver os resultados).
"""
import sys
import json
import statistics
sys.path.insert(0, '.')

import dspy

from src.config import setup, get_drift_thresholds
from src.drift.golden import GoldenSet
from src.drift.models import DriftThresholds
from src.infrastructure.dspy_impl import (
    AvaliadorModoBSignature as RulesSignature,
    DSPyAvaliadorModoB,
    _parse_manteve_regras,
    _parse_defeitos,
)
from src.infrastructure.enhanced_judge import EnhancedJudge
from src.signatures import AvaliacaoModoB, calcular_composite


# ── (a) Signature SEM Rules (baseline limpa) ──────────────

class BaselineSignature(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA e estruturalmente superior a original (Modo B - Caca-Defeitos).
    Analisa 6 dimensoes: clareza, formatacao, robustez, densidade informacional, acionabilidade, anti-fragilidade.
    Enumere contradicoes e defeitos primeiro.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restricoes ou metricas extras.")

    manteve_regras_criticas: str = dspy.OutputField(desc="True se nenhuma regra vital foi omitida. False caso contrario.")
    defeitos_encontrados: str = dspy.OutputField(desc="Violaçoes, paradoxos e ambiguidades detectadas. Enumere cada defeito.")
    nota_clareza: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a instrucao e clara e direta.")
    nota_formatacao: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.")
    nota_robustez: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.")
    nota_densidade_informacional: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando a razao sinal/ruido.")
    nota_acionabilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a instrucao e acionavel sem ambiguidade.")
    nota_anti_fragilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando resistencia a edge cases.")
    feedback_detalhado: str = dspy.OutputField(desc="Explicacao detalhada dos pontos fortes e fracos.")


class BaselineJudge:
    """Juiz SEM Rules — usa BaselineSignature pura."""
    def __init__(self):
        self._predictor = dspy.Predict(BaselineSignature)

    def evaluate(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'
        res = self._predictor(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais
        )
        defeitos_list = _parse_defeitos(getattr(res, 'defeitos_encontrados', ''))
        return AvaliacaoModoB(
            manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
            defeitos_encontrados=defeitos_list,
            nota_clareza=res.nota_clareza,
            nota_formatacao=res.nota_formatacao,
            nota_robustez=res.nota_robustez,
            nota_densidade_informacional=res.nota_densidade_informacional,
            nota_acionabilidade=res.nota_acionabilidade,
            nota_anti_fragilidade=res.nota_anti_fragilidade,
            feedback_detalhado=res.feedback_detalhado,
        )


# ── (b) Rules-only judge ──────────────────────────────────

class RulesOnlyJudge:
    """
    Juiz com Rules na docstring, SEM Metrics, SEM Swap.
    EXATAMENTE o que esta em producao agora (AvaliadorModoBSignature alterado na Fase 2).
    """
    def __init__(self):
        self._predictor = dspy.Predict(RulesSignature)

    def evaluate(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'
        res = self._predictor(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais
        )
        defeitos_list = _parse_defeitos(getattr(res, 'defeitos_encontrados', ''))
        return AvaliacaoModoB(
            manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
            defeitos_encontrados=defeitos_list,
            nota_clareza=res.nota_clareza,
            nota_formatacao=res.nota_formatacao,
            nota_robustez=res.nota_robustez,
            nota_densidade_informacional=res.nota_densidade_informacional,
            nota_acionabilidade=res.nota_acionabilidade,
            nota_anti_fragilidade=res.nota_anti_fragilidade,
            feedback_detalhado=res.feedback_detalhado,
        )


# ── Measurement helpers ───────────────────────────────────

def measure_config(label: str, judge_obj, golden: GoldenSet, repetitions: int) -> dict:
    """
    Mede uma configuracao contra todos os probes.
    Retorna dict com style_gap (media + stdev), per-probe composites, false_rejections, missed_violations.
    """
    results = {}
    style_gaps_list = []

    for probe in golden.probes:
        composites = []
        critical_oks = []
        for _ in range(repetitions):
            try:
                if hasattr(judge_obj, 'evaluate'):
                    result = judge_obj.evaluate(
                        skill_original=probe.skill_original,
                        skill_otimizada=probe.skill_otimizada,
                        regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                    )
                elif hasattr(judge_obj, '__call__'):
                    result = judge_obj(
                        skill_original=probe.skill_original,
                        skill_otimizada=probe.skill_otimizada,
                        regras_adicionais=probe.regras_adicionais or 'Preservar todas as regras comportamentais anteriores.',
                    )
                else:
                    raise TypeError(f"Judge object has no evaluate or __call__ method: {type(judge_obj)}")
                comp = calcular_composite(result)
                composites.append(comp)
                critical_oks.append(result.manteve_regras_criticas == probe.expected.manteve_regras_criticas)
            except Exception as e:
                print(f"  [!] {label} / {probe.id}: erro — {e}")
                composites.append(0.0)
                critical_oks.append(False)

        mean_comp = statistics.mean(composites) if composites else 0.0
        stdev_comp = statistics.pstdev(composites) if len(composites) >= 2 else 0.0
        expected_critical = probe.expected.manteve_regras_criticas

        results[probe.id] = {
            'mean_composite': mean_comp,
            'stdev_composite': stdev_comp,
            'expected_composite': probe.expected.composite_score(),
            'composites_raw': composites,
            'critical_ok_all': all(critical_oks),
            'expected_critical': expected_critical,
            'false_rejections': sum(1 for c in critical_oks if not c) if expected_critical else 0,
            'missed_violations': sum(1 for c in critical_oks if c) if not expected_critical else 0,
        }

    # style_gap: APENAS do par SD-1/SD-3 (ressalva 1)
    sd1_mean = results.get('SD-1', {}).get('mean_composite', 0.0)
    sd3_mean = results.get('SD-3', {}).get('mean_composite', 0.0)
    sd1_stdev = results.get('SD-1', {}).get('stdev_composite', 0.0)
    sd3_stdev = results.get('SD-3', {}).get('stdev_composite', 0.0)

    # Calcular style_gap por repeticao (para obter stdev do gap)
    sd1_raw = results.get('SD-1', {}).get('composites_raw', [])
    sd3_raw = results.get('SD-3', {}).get('composites_raw', [])
    if len(sd1_raw) == len(sd3_raw) and len(sd1_raw) > 0:
        gaps_per_rep = [sd1_raw[i] - sd3_raw[i] for i in range(len(sd1_raw))]
        gap_mean = statistics.mean(gaps_per_rep)
        gap_stdev = statistics.pstdev(gaps_per_rep) if len(gaps_per_rep) >= 2 else 0.0
    else:
        gap_mean = sd1_mean - sd3_mean
        gap_stdev = 0.0

    total_false_rej = sum(results[pid].get('false_rejections', 0) for pid in results)
    total_missed = sum(results[pid].get('missed_violations', 0) for pid in results)

    return {
        'label': label,
        'style_gap_mean': gap_mean,
        'style_gap_stdev': gap_stdev,
        'sd1_composite': sd1_mean,
        'sd1_stdev': sd1_stdev,
        'sd3_composite': sd3_mean,
        'sd3_stdev': sd3_stdev,
        'total_false_rejections': total_false_rej,
        'total_missed_violations': total_missed,
        'per_probe': results,
    }


# ── Main ─────────────────────────────────────────────────

def main():
    golden = GoldenSet()
    if golden.is_empty():
        print("[!] Golden set vazio. Abortando.")
        return

    repetitions = 5
    print(f"[*] Golden set: {len(golden.probes)} probes, {repetitions} repeticoes cada")
    for p in golden.probes:
        print(f"    {p.id}: category={p.category}, rank_band={p.expected_rank_band}, composite={p.expected.composite_score():.3f}")

    lm = setup()
    dspy.settings.configure(lm=lm)

    # ── (a) Baseline ──
    print("\n" + "=" * 60)
    print("(a) BASELINE — Sem Rules, Sem Metrics, Sem Swap")
    print("=" * 60)
    baseline = BaselineJudge()
    result_a = measure_config("(a) Baseline", baseline, golden, repetitions)

    # ── (b) Rules only ──
    print("\n" + "=" * 60)
    print("(b) RULES ONLY — So Rules na docstring (producao atual)")
    print("=" * 60)
    rules_only = RulesOnlyJudge()
    result_b = measure_config("(b) Rules only", rules_only, golden, repetitions)

    # ── (c) EnhancedJudge (Rules + Metrics + Swap) ──
    print("\n" + "=" * 60)
    print("(c) ENHANCED — Rules + Metrics + Swap")
    print("=" * 60)
    base_judge_c = DSPyAvaliadorModoB()
    enhanced = EnhancedJudge(base_judge_c)
    result_c = measure_config("(c) Enhanced", enhanced, golden, repetitions)

    # ── Report ──
    print("\n" + "=" * 70)
    print("RESULTADOS: Isolamento de Componentes — Style Gap")
    print("=" * 70)
    print(f"\n{'Configuracao':<30} {'style_gap':>10} {'±stdev':>10} {'SD-1':>8} {'SD-3':>8} {'FalseRej':>10} {'MissedV':>10}")
    print("-" * 86)

    for r in [result_a, result_b, result_c]:
        print(f"{r['label']:<30} {r['style_gap_mean']:>10.3f} {r['style_gap_stdev']:>10.3f} {r['sd1_composite']:>8.3f} {r['sd3_composite']:>8.3f} {r['total_false_rejections']:>10} {r['total_missed_violations']:>10}")

    # ── Análise ──
    print("\n" + "=" * 70)
    print("ANALISE (epsilon = 0.05)")
    print("=" * 70)

    gap_b = result_b['style_gap_mean']
    gap_c = result_c['style_gap_mean']
    diff = abs(gap_b - gap_c)

    print(f"  gap(Rules only)        = {gap_b:.3f} ± {result_b['style_gap_stdev']:.3f}")
    print(f"  gap(Rules+Metrics+Swap) = {gap_c:.3f} ± {result_c['style_gap_stdev']:.3f}")
    print(f"  |delta|                 = {diff:.3f}")
    print(f"  epsilon                 = 0.05")

    if diff < 0.05:
        print(f"\n  => Metrics e NEUTRO para style_gap (|delta| = {diff:.3f} < 0.05)")
    else:
        direction = "PIOROU" if gap_c < gap_b else "MELHOROU"
        print(f"\n  => Metrics {direction} o style_gap (|delta| = {diff:.3f} >= 0.05)")

    # Verificar se o desvio-padrao torna a conclusao fragil
    pooled_stdev = statistics.mean([result_b['style_gap_stdev'], result_c['style_gap_stdev']])
    if diff < pooled_stdev:
        print(f"  [!] ATENCAO: |delta| ({diff:.3f}) < desvio-padrao medio ({pooled_stdev:.3f}).")
        print(f"      A diferenca NAO e estatisticamente significativa — pode ser ruido.")

    # ── Salvar ──
    output = {
        'configurations': {
            'a_baseline': result_a,
            'b_rules_only': {k: v for k, v in result_b.items() if k != 'per_probe'},
            'c_enhanced': {k: v for k, v in result_c.items() if k != 'per_probe'},
        },
        'epsilon': 0.05,
        'significant': diff >= pooled_stdev,
        'per_probe_a': {k: {kk: vv for kk, vv in v.items() if kk != 'composites_raw'} for k, v in result_a['per_probe'].items()},
        'per_probe_b': {k: {kk: vv for kk, vv in v.items() if kk != 'composites_raw'} for k, v in result_b['per_probe'].items()},
        'per_probe_c': {k: {kk: vv for kk, vv in v.items() if kk != 'composites_raw'} for k, v in result_c['per_probe'].items()},
    }
    with open('src/outputs/golden/isolate_components.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n[*] Relatorio salvo em src/outputs/golden/isolate_components.json")


if __name__ == '__main__':
    main()