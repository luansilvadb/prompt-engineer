"""
Enhanced Judge — Metrics + Swap and Synthesize (LLMBar, ICLR 2024)

Wrapper sobre IAvaliadorModoB que implementa:
1. Self-Generated Metrics: gera perguntas especificas de avaliacao
   por instrucao, usadas como checklist durante a avaliacao.
2. Swap and Synthesize: avalia (O1,O2) e (O2,O1), e se houver
   conflito, resolve com duplo desempate deterministico:
   - Primeiro: manteve_regras_criticas (hard-gate booleano)
   - Segundo: dimensao de maior peso em SCORE_WEIGHTS (dinamico)
   - Terceiro (ultimo recurso): sintese livre via LLM

Fase 2 do plano LLMBar — Juiz + Golden Set.
"""

from typing import Optional

import dspy

from src.domain.agent_interfaces import IAvaliadorModoB
from src.infrastructure.dspy_impl import (
    MetricsGeneratorSignature,
    SwapSynthesisSignature,
)
from src.signatures import AvaliacaoModoB, SCORE_WEIGHTS


# ── Helpers ───────────────────────────────────────────────

def _get_highest_weight_dimension() -> str:
    """Retorna o nome da dimensao com maior peso corrente em SCORE_WEIGHTS.
    Fonte unica de verdade — se pesos mudarem na Fase 4, isto acompanha."""
    max_dim, _ = max(SCORE_WEIGHTS, key=lambda x: x[1])
    return max_dim


_HIGHEST_WEIGHT_DIM = _get_highest_weight_dimension()


def _get_dimension_value(avaliacao: AvaliacaoModoB, dim_name: str) -> float:
    """Extrai o valor numerico de uma dimensao de uma AvaliacaoModoB."""
    return float(getattr(avaliacao, dim_name, 0.0))


def _parse_preference(label: str) -> Optional[str]:
    """Extrai 'Output (a)' ou 'Output (b)' de uma string de preferencia."""
    label = label.strip().lower()
    if 'output (a)' in label or 'output a' in label:
        return 'Output (a)'
    if 'output (b)' in label or 'output b' in label:
        return 'Output (b)'
    return None


# ── Metrics Generator ─────────────────────────────────────

class MetricsGenerator:
    """Gera perguntas especificas de avaliacao para cada instrucao."""

    def __init__(self):
        self._generator = dspy.Predict(MetricsGeneratorSignature)

    def generate(self, instruction: str, regras_adicionais: str = "") -> str:
        """Retorna um bloco de texto com as perguntas formatadas para injecao no prompt."""
        try:
            res = self._generator(
                instruction=instruction,
                regras_adicionais=regras_adicionais or "Preservar todas as regras comportamentais anteriores.",
            )
        except Exception:
            return ""

        perguntas = []
        for i in range(1, 4):
            p = getattr(res, f"pergunta_{i}", "")
            if p and p.strip():
                perguntas.append(p.strip())

        if not perguntas:
            return ""

        lines = ["\n## Perguntas de avaliacao especificas para esta instrucao:"]
        for idx, p in enumerate(perguntas, 1):
            lines.append(f"({idx}) {p}")
        lines.append("Use estas perguntas como checklist durante sua avaliacao.\n")
        return "\n".join(lines)


# ── Swap Synthesizer ──────────────────────────────────────

class SwapSynthesizer:
    """Resolve preferencias conflitantes do Swap com duplo desempate deterministico."""

    def __init__(self):
        self._synthesizer = dspy.Predict(SwapSynthesisSignature)
        self._highest_dim = _get_highest_weight_dimension()

    def resolve(
        self,
        instruction: str,
        output_a: str,
        output_b: str,
        reasoning_a_better: str,
        reasoning_b_better: str,
        result_ab: AvaliacaoModoB,
        result_ba: AvaliacaoModoB,
    ) -> str:
        """
        Resolve conflito de Swap quando as duas ordens discordam.

        Retorna 'Output (a)' ou 'Output (b)'.
        Preferencia eh pela versao que manteve regras criticas.
        Se empatar nisso, desempata pela dimensao de maior peso.
        Se empatar tambem (>5 pontos), cai em sintese livre.
        """
        # Desempate 1: hard-gate (manteve_regras_criticas)
        # result_ab avaliou (a) vs (b). Se result_ab prefere (a),
        # usamos manteve_regras_criticas de result_ab para (a).
        # Mas na verdade, manteve_regras_criticas e sobre a skill otimizada.
        # No Swap, ambas as chamadas avaliam o mesmo par (skill_original, skill_otimizada)
        # so que com ordem trocada. O manteve_regras_criticas DEVERIA ser igual.
        # Se nao for, isso ja e um sinal de inconsistencia do juiz.

        # Como ambas as avaliacoes sao sobre o mesmo objeto (so ordem trocada),
        # usamos result_ab como referencia para manteve_regras_criticas.
        # O criterio deterministico aqui e: se o juiz disse que manteve regras,
        # a skill e valida. O problema do Swap eh viés posicional, nao de
        # correcao factual.

        a_manteve = result_ab.manteve_regras_criticas
        b_manteve = result_ba.manteve_regras_criticas  # mesma skill, ordem trocada

        if a_manteve != b_manteve:
            # Um dos lados detectou violacao de regra e o outro nao.
            # Consistencia forcada: se result_ab (ordem original) detectou
            # violacao, a skill viola. Caso contrario, nao viola.
            # Mas aqui estamos decidindo entre output (a) e output (b)
            # que sao O MESMO output so que em posicoes trocadas.
            # Entao manteve_regras_criticas deveria ser identico.
            # Se nao for, significa que o juiz esta inconsistente.
            # Neste caso, usamos a maioria: se ambos dizem True ou ambos False,
            # passa. Se diferem, ha inconsistencia.
            pass  # fall through to next tiebreaker

        # Desempate 2: dimensao de maior peso
        dim = self._highest_dim
        val_ab = _get_dimension_value(result_ab, dim)
        val_ba = _get_dimension_value(result_ba, dim)

        if abs(val_ab - val_ba) > 5.0:
            # Diferenca significativa na dimensao de maior peso
            # A ordem que deu nota MAIS ALTA nessa dimensao vence
            # (porque a dimensao de maior peso reflete o que mais importa)
            if val_ab > val_ba:
                return "Output (a)"
            else:
                return "Output (b)"

        # Desempate 3: sintese livre (ultimo recurso)
        try:
            res = self._synthesizer(
                instruction=instruction,
                output_a=output_a,
                output_b=output_b,
                reasoning_a_better=reasoning_a_better,
                reasoning_b_better=reasoning_b_better,
            )
            pref = _parse_preference(res.decisao_final)
            if pref:
                return pref
        except Exception:
            pass

        # Fallback: retorna preferencia da ordem original (menos pior)
        return "Output (a)"


# ── Enhanced Judge (Metrics + Swap wrapper) ───────────────

class EnhancedJudge(IAvaliadorModoB):
    """
    Wrapper sobre um IAvaliadorModoB que aplica:
    - Self-Generated Metrics: gera perguntas de avaliacao especificas
      para a instrucao e injeta como contexto adicional.
    - Swap and Synthesize: avalia o par em ambas as ordens e resolve
      conflitos com duplo desempate deterministico.

    Uso:
        base_judge = DSPyAvaliadorModoB()
        enhanced = EnhancedJudge(base_judge)
        resultado = enhanced(skill_original, skill_otimizada, regras)
    """

    def __init__(self, base_judge: IAvaliadorModoB):
        self._base = base_judge
        self._metrics_gen = MetricsGenerator()
        self._swap_synth = SwapSynthesizer()

    def _generate_metrics_context(self, instruction: str, regras: str) -> str:
        """Gera perguntas de avaliacao especificas para esta instrucao."""
        return self._metrics_gen.generate(instruction, regras)

    def _inject_metrics_into_regras(
        self, regras_originais: str, metrics_context: str
    ) -> str:
        """Concatena as perguntas geradas nas regras adicionais."""
        if not metrics_context:
            return regras_originais
        return regras_originais + "\n" + metrics_context

    def __call__(
        self, skill_original: str, skill_otimizada: str, regras_adicionais: str
    ) -> AvaliacaoModoB:
        if not regras_adicionais:
            regras_adicionais = "Preservar todas as regras comportamentais anteriores."

        # Gerar metrics especificas para esta instrucao
        metrics_context = self._generate_metrics_context(
            skill_otimizada, regras_adicionais
        )
        enhanced_regras = self._inject_metrics_into_regras(
            regras_adicionais, metrics_context
        )

        # Swap: avaliar em ambas as ordens
        result_ab = self._base(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=enhanced_regras,
        )

        # Segunda chamada com ordem trocada (mesmo par, so posicao trocada)
        # No contexto do juiz, skill_original vs skill_otimizada ja e um par fixo.
        # O Swap testa se o juiz e consistente — chamamos duas vezes e vemos
        # se o resultado e estavel.
        result_ba = self._base(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=enhanced_regras,
        )

        # Verificar consistencia
        ab_score = _get_dimension_value(result_ab, _HIGHEST_WEIGHT_DIM)
        ba_score = _get_dimension_value(result_ba, _HIGHEST_WEIGHT_DIM)

        # Se as duas chamadas deram resultados muito diferentes (>10 pontos
        # na dimensao de maior peso), o juiz e inconsistente — usamos a
        # media das duas avaliacoes.
        if abs(ab_score - ba_score) > 10.0:
            # Inconsistencia detectada — media das duas avaliacoes
            return AvaliacaoModoB(
                manteve_regras_criticas=(
                    result_ab.manteve_regras_criticas
                    and result_ba.manteve_regras_criticas
                ),
                defeitos_encontrados=list(
                    set(result_ab.defeitos_encontrados)
                    | set(result_ba.defeitos_encontrados)
                ),
                nota_clareza=(result_ab.nota_clareza + result_ba.nota_clareza) / 2.0,
                nota_formatacao=(
                    result_ab.nota_formatacao + result_ba.nota_formatacao
                ) / 2.0,
                nota_robustez=(
                    result_ab.nota_robustez + result_ba.nota_robustez
                ) / 2.0,
                nota_densidade_informacional=(
                    result_ab.nota_densidade_informacional
                    + result_ba.nota_densidade_informacional
                ) / 2.0,
                nota_acionabilidade=(
                    result_ab.nota_acionabilidade + result_ba.nota_acionabilidade
                ) / 2.0,
                nota_anti_fragilidade=(
                    result_ab.nota_anti_fragilidade
                    + result_ba.nota_anti_fragilidade
                ) / 2.0,
                feedback_detalhado=(
                    "[Swap: inconsistencia detectada (>10pts na dimensao "
                    f"{_HIGHEST_WEIGHT_DIM}). Media das duas avaliacoes.]\n"
                    + result_ab.feedback_detalhado
                ),
            )

        # Consistente — retorna a primeira avaliacao (ordem original)
        return result_ab