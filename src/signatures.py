import re
from dataclasses import dataclass

@dataclass
class RaciocinioCognitivo:
    """
    premissas: Premissas extraídas do feedback e da instrução atual.
    deducoes: Deduções e implicações lógicas derivadas das premissas.
    conclusao: Conclusão acionável — o que a nova instrução DEVE fazer diferente.
    """
    premissas: str
    deducoes: str
    conclusao: str

    def __post_init__(self):
        for v in (self.premissas, self.deducoes, self.conclusao):
            if not v or len(v.strip()) < 10:
                raise ValueError("Campo obrigatório do raciocínio estruturado está vazio ou genérico.")


@dataclass
class MutadorCognitivoOutput:
    """
    nova_instrucao: A nova skill reescrita com seções cognitivas obrigatórias.
    """
    nova_instrucao: str

    def __post_init__(self):
        v = self.nova_instrucao
        normalized = v.lower()
        required = ['## raciocínio', '## regras', '## conclusão']
        missing = [s for s in required if s not in normalized]
        if missing:
            raise ValueError(f"nova_instrucao deve conter as seções: {missing}")
        if len(v.strip()) < 50:
            raise ValueError("nova_instrucao muito curta para conter derivação cognitiva completa.")


def _validate_raciocinio(raciocinio_str: str) -> None:
    """Valida e extrai as seções obrigatórias do raciocínio estruturado."""
    sections = {
        'premissas': r'(?i)premissas\s*[:：]?\s*',
        'deducoes': r'(?i)dedu(?:ç[õo]es|coes|)\s*[:：]?\s*',
        'conclusao': r'(?i)conclus[ãa]o\s*[:：]?\s*',
    }

    extracted = {}
    last_end = 0
    ordered = list(sections.items())

    for i, (key, pattern) in enumerate(ordered):
        match = re.search(pattern, raciocinio_str[last_end:])
        if not match:
            raise ValueError(f"raciocinio_estruturado está faltando a seção obrigatória: {key}")
        start = last_end + match.end()
        if i + 1 < len(ordered):
            next_pattern = ordered[i + 1][1]
            next_match = re.search(next_pattern, raciocinio_str[start:])
            end = start + next_match.start() if next_match else len(raciocinio_str)
        else:
            end = len(raciocinio_str)
        extracted[key] = raciocinio_str[start:end].strip()
        last_end = start

    RaciocinioCognitivo(
        premissas=extracted['premissas'],
        deducoes=extracted['deducoes'],
        conclusao=extracted['conclusao'],
    )


@dataclass
class Avaliacao:
    """
    manteve_regras_criticas: True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.
    nota_clareza: Nota de 0 a 100 avaliando se a instrução é clara e direta.
    nota_formatacao: Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.
    nota_robustez: Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.
    nota_densidade_informacional: Nota de 0 a 100 avaliando a razão sinal/ruído — penaliza verbosidade vazia e repetição sem valor.
    nota_acionabilidade: Nota de 0 a 100 avaliando se as instruções são claras o suficiente para um agente de IA executar sem ambiguidade.
    nota_anti_fragilidade: Nota de 0 a 100 avaliando se a skill resiste a edge cases, inputs adversariais e contextos ambíguos.
    feedback_detalhado: Explicação detalhada dos pontos fortes e fracos, justificando as notas.
    """
    manteve_regras_criticas: bool
    nota_clareza: float
    nota_formatacao: float
    nota_robustez: float
    nota_densidade_informacional: float
    nota_acionabilidade: float
    nota_anti_fragilidade: float
    feedback_detalhado: str

    def __post_init__(self):
        import re
        notas = [
            'nota_clareza', 'nota_formatacao', 'nota_robustez',
            'nota_densidade_informacional', 'nota_acionabilidade',
            'nota_anti_fragilidade'
        ]
        for attr in notas:
            v = getattr(self, attr)
            if isinstance(v, str):
                match = re.search(r'\d+(?:\.\d+)?', v)
                if match:
                    v = match.group(0)
            try:
                v_float = float(v)
            except (ValueError, TypeError):
                raise ValueError("A nota deve ser um número numérico.")
            if v_float < 0 or v_float > 100:
                raise ValueError("A nota deve estar rigorosamente entre 0 e 100.")
            setattr(self, attr, v_float)

@dataclass
class AvaliacaoModoB(Avaliacao):
    """
    defeitos_encontrados: Lista de strings enumerando violações, paradoxos e ambiguidades detectadas.
    """
    defeitos_encontrados: list[str]


def _check_critical_rules(resultado: Avaliacao) -> bool:
    return resultado.manteve_regras_criticas

# Tabela única de pesos das 6 dimensões (DRY — única fonte de verdade).
# Robustez e acionabilidade valem mais (são os mais críticos para que a
# skill funcione num agente real). drift_monitor importa esta constante.
SCORE_WEIGHTS: tuple = (
    ('nota_clareza', 1.0),
    ('nota_formatacao', 0.8),
    ('nota_robustez', 1.2),
    ('nota_densidade_informacional', 1.4),  # Fase 4: aumentado de 1.0 — dimensão mais vulnerável ao viés estético
    ('nota_acionabilidade', 1.4),           # Fase 4: aumentado de 1.3 — instruction following objetivo
    ('nota_anti_fragilidade', 1.2),
)
# NOTA (DESIGN.md): pesos acima são valores iniciais calibrados na Fase 4 (LLMBar).
# Após golden set expandido para 21+ probes, reavaliar com MAE-driven adjustment:
# weight_new = weight_old * (1 + MAE_normalized), renormalizar.
# ANTES do ajuste automático: inspecionar manualmente dimensões com MAE no quartil superior.
# Se ≥2 dos 3 probes com maior desvio forem erro de calibração do golden set,
# corrigir o golden set, NÃO os pesos.


def calcular_composite(notas) -> float:
    """
    Calcula score composicional de 6 dimensões a partir de qualquer objeto
    que exponha os atributos nota_clareza..nota_anti_fragilidade (Avaliacao,
    ProbeExpectation, dict-like). Reutilizado por _calculate_score e pelo
    drift_monitor — nunca duplicar a tabela de pesos (Norma 2).
    """
    total_weight = sum(w for _, w in SCORE_WEIGHTS)
    weighted_sum = 0.0

    for field, weight in SCORE_WEIGHTS:
        raw = getattr(notas, field, 0.0)
        clamped = max(0.0, min(100.0, raw))
        weighted_sum += (clamped / 100.0) * weight

    return weighted_sum / total_weight


def _calculate_score(resultado: Avaliacao) -> float:
    """
    Calcula score composicional de 6 dimensões.
    Delega para calcular_composite (fonte única de pesos).
    """
    return calcular_composite(resultado)


def calcular_delta_reward(reward_filho: float, reward_pai: float, alpha: float = 0.6) -> float:
    """
    Reward shaping com delta comparativo.
    
    Silver: temporal-difference é melhor que Monte-Carlo para avaliação incremental.
    
    O reward final combina:
    - alpha * reward_absoluto (qualidade intrínseca)
    - (1-alpha) * delta (quanto melhorou vs. pai)
    
    Isso estabiliza o aprendizado e dá crédito proporcional à melhoria.
    """
    delta = reward_filho - reward_pai
    # Bônus/penalidade pelo delta, normalizado.
    # Permitir delta negativo para que o bandit aprenda com pioras.
    shaped = alpha * reward_filho + (1 - alpha) * delta
    return max(0.0, min(1.0, shaped))

def funcao_de_recompensa(avaliador_modo_b, skill_original: str, skill_otimizada: str, regras_adicionais: str):
    """
    Reward function composicional com 6 dimensões.
    Retorna (score, feedback) onde score ∈ [0, 1].
    """
    try:
        resultado = avaliador_modo_b(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais
        )

        if not _check_critical_rules(resultado):
            return 0.0, resultado.feedback_detalhado

        score = _calculate_score(resultado)

        if resultado.defeitos_encontrados:
            # BUG-4 fix: teto de 0.5 evita colapso catastrófico por defeitos cosméticos.
            # Sem teto, 6 defeitos leves → penalty=0.6 e score 0.80 vira 0.20.
            penalty = min(len(resultado.defeitos_encontrados) * 0.1, 0.5)
            score = max(0.0, score - penalty)

            bullet_points = "\\n".join(f"- {d}" for d in resultado.defeitos_encontrados)
            feedback = f"DEFEITOS E CONTRADIÇÕES ENCONTRADAS:\\n{bullet_points}\\n\\nCorrija as quebras arquiteturais acima urgentemente."
            return score, feedback

        return score, resultado.feedback_detalhado
    except Exception as e:
        return 0.0, f'Erro interno na avaliação: {str(e)}'
