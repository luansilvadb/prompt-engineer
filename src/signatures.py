import dspy
from pathlib import Path
from pydantic import BaseModel, Field, field_validator

class GeracaoSkill(BaseModel):
    critica: str = Field(description="Análise do feedback e proposta de qual nova abordagem testar (proibido dizer que está perfeito).")
    nova_instrucao: str = Field(description="A nova skill reescrita e otimizada, formatada em Markdown.")

    @field_validator('nova_instrucao')
    def validar_tamanho_instrucao(cls, v):
        if len(v.strip()) < 50:
            raise ValueError("A nova instrução gerada é muito curta. Forneça uma skill completa e detalhada baseada nas estratégias e feedbacks.")
        return v

class StrategyDiscoverer(dspy.Signature):
    """Analisa o contexto atual (a skill, as falhas passadas, e o que já foi tentado) e INVENTA uma heurística de mutação totalmente nova e criativa para quebrar o platô atual."""
    skill_atual: str = dspy.InputField(desc="O estado atual da instrução que estamos tentando melhorar.")
    feedbacks_recentes: str = dspy.InputField(desc="Resumo das críticas mais recentes, o que está falhando?")
    estrategias_conhecidas: str = dspy.InputField(desc="Lista das estratégias que o sistema já conhece. VOCÊ NÃO PODE REPETIR ESTAS.")
    nome_estrategia: str = dspy.OutputField(desc="Um nome curto e impactante para sua nova estratégia (ex: 'Paradoxo de Exclusão').")
    prompt_estrategia: str = dspy.OutputField(desc="O prompt detalhado descrevendo exatamente COMO aplicar esta estratégia. Deve ser imperativo e focado (ex: 'Reescreva tudo removendo...').")

class SelfReflectiveAgent(dspy.Signature):
    """Analisa uma instrução avaliada. OBRIGATÓRIO: Mesmo que a nota seja altíssima, você DEVE propor uma reescrita usando uma abordagem diferente, testando novos formatos ou tons arquiteturais. É PROIBIDO dizer que a instrução atual está perfeita e recusar-se a alterá-la."""
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField(desc="Feedback detalhado do avaliador explicando os motivos da nota.")
    estrategia_mutacao: str = dspy.InputField(desc="Estratégia de mutação a ser aplicada nesta iteração. Siga rigorosamente a diretriz.")
    critica: str = dspy.OutputField(desc="Análise do feedback e proposta de qual nova abordagem testar (proibido dizer que está perfeito).")
    nova_instrucao: str = dspy.OutputField(desc="A nova skill reescrita e otimizada, formatada em Markdown.")

class Avaliacao(BaseModel):
    manteve_regras_criticas: bool = Field(description="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    nota_clareza: float = Field(description="Nota de 0 a 100 avaliando se a instrução é clara e direta.")
    nota_formatacao: float = Field(description="Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.")
    nota_robustez: float = Field(description="Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.")
    nota_densidade_informacional: float = Field(description="Nota de 0 a 100 avaliando a razão sinal/ruído — penaliza verbosidade vazia e repetição sem valor.")
    nota_acionabilidade: float = Field(description="Nota de 0 a 100 avaliando se as instruções são claras o suficiente para um agente de IA executar sem ambiguidade.")
    nota_anti_fragilidade: float = Field(description="Nota de 0 a 100 avaliando se a skill resiste a edge cases, inputs adversariais e contextos ambíguos.")
    feedback_detalhado: str = Field(description="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")

    @field_validator('nota_clareza', 'nota_formatacao', 'nota_robustez', 'nota_densidade_informacional', 'nota_acionabilidade', 'nota_anti_fragilidade', mode='before')
    @classmethod
    def validar_nota(cls, v):
        import re
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
        return v_float

class AvaliadorDeSkill(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA é estruturalmente superior à original.
    Analisa 6 dimensões ortogonais: clareza, formatação, robustez, densidade informacional,
    acionabilidade e anti-fragilidade. Todas as regras exigidas devem ser cumpridas.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restrições ou métricas extras especificadas pelo usuário que devem ser estritamente seguidas.")
    
    manteve_regras_criticas: str = dspy.OutputField(desc="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    nota_clareza: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a instrução é clara e direta.")
    nota_formatacao: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.")
    nota_robustez: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.")
    nota_densidade_informacional: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando a razão sinal/ruído — penaliza verbosidade vazia e repetição sem valor.")
    nota_acionabilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se as instruções são claras o suficiente para um agente de IA executar sem ambiguidade.")
    nota_anti_fragilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a skill resiste a edge cases, inputs adversariais e contextos ambíguos.")
    feedback_detalhado: str = dspy.OutputField(desc="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")

avaliador_module = dspy.Predict(AvaliadorDeSkill)

def load_avaliador():
    model_path = Path('src/outputs/models/avaliador_otimizado.json')
    if model_path.exists():
        try:
            avaliador_module.load(str(model_path))
            print(f"[*] Avaliador otimizado (Few-Shot) carregado de {model_path}.")
        except Exception as e:
            print(f"[!] Erro ao carregar avaliador otimizado: {e}")

def _invoke_judge(exemplo, predicao) -> Avaliacao:
    """Invoca o módulo juiz GLOBAL (avaliador_module). Mantido para compat."""
    return _invoke_judge_with(avaliador_module, exemplo, predicao)


def _invoke_judge_with(module, exemplo, predicao) -> Avaliacao:
    """
    Invoca um módulo juiz ESPECÍFICO sobre (exemplo, predicao).
    Parametrizado para permitir que o drift_monitor meça juizes isolados
    (candidato / atual / zerado) sem tocar no módulo global avaliador_module.
    """
    regras = getattr(exemplo, 'regras_adicionais', '')
    if not regras:
        regras = 'Preservar todas as regras comportamentais anteriores.'

    res = module(
        skill_original=exemplo.skill_original,
        skill_otimizada=predicao.skill_otimizada,
        regras_adicionais=regras
    )
    
    manteve_str = str(res.manteve_regras_criticas).strip().lower()
    manteve_val = 'true' in manteve_str or 'sim' in manteve_str or 'yes' in manteve_str or manteve_str == '1'
    
    return Avaliacao(
        manteve_regras_criticas=manteve_val,
        nota_clareza=res.nota_clareza,
        nota_formatacao=res.nota_formatacao,
        nota_robustez=res.nota_robustez,
        nota_densidade_informacional=res.nota_densidade_informacional,
        nota_acionabilidade=res.nota_acionabilidade,
        nota_anti_fragilidade=res.nota_anti_fragilidade,
        feedback_detalhado=res.feedback_detalhado
    )

def _check_critical_rules(resultado: Avaliacao) -> bool:
    return resultado.manteve_regras_criticas

# Tabela única de pesos das 6 dimensões (DRY — única fonte de verdade).
# Robustez e acionabilidade valem mais (são os mais críticos para que a
# skill funcione num agente real). drift_monitor importa esta constante.
SCORE_WEIGHTS: tuple = (
    ('nota_clareza', 1.0),
    ('nota_formatacao', 0.8),
    ('nota_robustez', 1.2),
    ('nota_densidade_informacional', 1.0),
    ('nota_acionabilidade', 1.3),
    ('nota_anti_fragilidade', 1.2),
)


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

def funcao_de_recompensa(exemplo, predicao, trace=None):
    """
    Reward function composicional com 6 dimensões.
    Retorna (score, feedback) onde score ∈ [0, 1].
    """
    try:
        resultado = _invoke_judge(exemplo, predicao)
        
        if not _check_critical_rules(resultado):
            return 0.0, resultado.feedback_detalhado
            
        score = _calculate_score(resultado)
        return score, resultado.feedback_detalhado
    except Exception as e:
        return 0.0, f'Erro interno na avaliação: {str(e)}'


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
    # Bônus/penalidade pelo delta, normalizado
    shaped = alpha * reward_filho + (1 - alpha) * max(0.0, delta)
    return max(0.0, min(1.0, shaped))
