"""Configuracao (d): BaselineSignature + 4 regras, sem framing Modo B."""
import sys
sys.path.insert(0, '.')

import dspy

from src.config import setup
from src.drift.golden import GoldenSet
from src.infrastructure.dspy_impl import _parse_manteve_regras, _parse_defeitos
from src.signatures import AvaliacaoModoB, calcular_composite


class ControlledSignature(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA e estruturalmente superior a original.
    Analisa 6 dimensoes: clareza, formatacao, robustez, densidade informacional, acionabilidade, anti-fragilidade.
    Enumere contradicoes e defeitos primeiro.

    REGRAS DE AVALIACAO (OBRIGATORIO seguir):
    (1) PRIORIZE instruction following sobre estilo superficial.
        Um output que executa precisamente a instrucao e SEMPRE melhor
        que um output com tom polido mas que desvia do solicitado.
    (2) Vocabulario pomposo sem substancia DEVE ser penalizado na nota
        de densidade informacional.
    (3) Outputs com MAIS ou MENOS conteudo que o solicitado sao piores,
        independente da qualidade do conteudo extra.
    (4) Output (a) e Output (b) sao igualmente provaveis de ser o melhor.
        Nao favoreca o primeiro output apresentado.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restricoes ou metricas extras.")
    manteve_regras_criticas: str = dspy.OutputField(desc="True se nenhuma regra vital foi omitida.")
    defeitos_encontrados: str = dspy.OutputField(desc="Violacoes, paradoxos e ambiguidades detectadas.")
    nota_clareza: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando clareza.")
    nota_formatacao: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando formatacao.")
    nota_robustez: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando robustez.")
    nota_densidade_informacional: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando densidade informacional.")
    nota_acionabilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando acionabilidade.")
    nota_anti_fragilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando anti-fragilidade.")
    feedback_detalhado: str = dspy.OutputField(desc="Explicacao detalhada.")


def main():
    golden = GoldenSet()
    lm = setup()
    dspy.settings.configure(lm=lm)

    predictor = dspy.Predict(ControlledSignature)
    regras = "Preservar todas as regras comportamentais anteriores."

    print("=== (d) Controlled: BaselineSignature + 4 rules (sem framing Modo B) ===")
    results = {}

    for pid in ["SD-1", "SD-3"]:
        probe = [p for p in golden.probes if p.id == pid][0]
        res = predictor(
            skill_original=probe.skill_original,
            skill_otimizada=probe.skill_otimizada,
            regras_adicionais=regras,
        )
        comp = calcular_composite(
            AvaliacaoModoB(
                manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
                defeitos_encontrados=_parse_defeitos(getattr(res, "defeitos_encontrados", "")),
                nota_clareza=res.nota_clareza,
                nota_formatacao=res.nota_formatacao,
                nota_robustez=res.nota_robustez,
                nota_densidade_informacional=res.nota_densidade_informacional,
                nota_acionabilidade=res.nota_acionabilidade,
                nota_anti_fragilidade=res.nota_anti_fragilidade,
                feedback_detalhado=res.feedback_detalhado,
            )
        )
        results[pid] = {
            "composite": comp,
            "nota_densidade_informacional": float(res.nota_densidade_informacional),
            "nota_acionabilidade": float(res.nota_acionabilidade),
            "nota_clareza": float(res.nota_clareza),
        }
        print(
            f"  {pid}: composite={comp:.3f}  "
            f"densidade={res.nota_densidade_informacional}  "
            f"acionabilidade={res.nota_acionabilidade}  "
            f"clareza={res.nota_clareza}  "
            f"manteve={_parse_manteve_regras(res.manteve_regras_criticas)}"
        )

    sd1 = results.get("SD-1", {}).get("composite", 0)
    sd3 = results.get("SD-3", {}).get("composite", 0)
    gap_d = sd1 - sd3

    print(f"\n(d) Controlled gap: {gap_d:.3f}")
    print()
    print("=== Decomposicao ===")
    print(f"  (a) Baseline pura:           gap=0.074 (SD-1=0.949, SD-3=0.874)")
    print(f"  (d) Baseline + 4 regras:     gap={gap_d:.3f} (SD-1={sd1:.3f}, SD-3={sd3:.3f})")
    print(f"  (b) Rules-only (Modo B):     gap=0.599 (SD-1=0.939, SD-3=0.340)")
    print(f"  (c) Enhanced:                gap=0.399 (SD-1=0.974, SD-3=0.576)")
    print()
    print(f"  (d)-(a) = efeito isolado das 4 regras (sem framing)    = {gap_d - 0.074:+.3f}")
    print(f"  (b)-(d) = efeito residual do framing 'Modo B'         = {0.599 - gap_d:+.3f}")
    print(f"  (b)-(a) = efeito total (regras + framing)              = {0.599 - 0.074:+.3f}")
    print(f"  (b)-(c) = efeito de adicionar Metrics+Swap            = {0.599 - 0.399:+.3f}")

    # Check for interaction
    regras_alone = gap_d - 0.074
    framing_alone = 0.599 - gap_d
    total = 0.599 - 0.074
    interaction = total - (regras_alone + framing_alone)
    if abs(interaction) > 0.02:
        print(f"\n  [!] Interacao detectada: regras + framing nao sao puramente aditivos.")
        print(f"       Regras isoladas: {regras_alone:+.3f}")
        print(f"       Framing isolado: {framing_alone:+.3f}")
        print(f"       Soma: {regras_alone + framing_alone:+.3f}")
        print(f"       Total observado: {total:+.3f}")
        print(f"       Interacao: {interaction:+.3f}")


if __name__ == "__main__":
    main()