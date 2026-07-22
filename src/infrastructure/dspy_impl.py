import dspy
from pathlib import Path
from src.signatures import Avaliacao, AvaliacaoModoB, _sanitize_unicode_for_api
from src.domain.agent_interfaces import (
    DiscoveredStrategy,
    SelfReflectiveOutput,
    MutadorCognitivoAgentOutput,
    IStrategyDiscoverer,
    ISelfReflectiveAgent,
    IMutadorCognitivoAgent,
    IAvaliadorModoB
)

class StrategyDiscovererSignature(dspy.Signature):
    """Analisa o contexto atual (a skill, as falhas passadas, e o que já foi tentado) e INVENTA uma heurística de mutação totalmente nova e criativa para quebrar o platô atual."""
    skill_atual: str = dspy.InputField(desc="O estado atual da instrução que estamos tentando melhorar.")
    feedbacks_recentes: str = dspy.InputField(desc="Resumo das críticas mais recentes, o que está falhando?")
    estrategias_conhecidas: str = dspy.InputField(desc="Lista das estratégias que o sistema já conhece. VOCÊ NÃO PODE REPETIR ESTAS.")
    nome_estrategia: str = dspy.OutputField(desc="Um nome curto e impactante para sua nova estratégia (ex: 'Paradoxo de Exclusão').")
    prompt_estrategia: str = dspy.OutputField(desc="O prompt detalhado descrevendo exatamente COMO aplicar esta estratégia. Deve ser imperativo e focado (ex: 'Reescreva tudo removendo...').")

class SelfReflectiveAgentSignature(dspy.Signature):
    """Analisa uma instrução avaliada. OBRIGATÓRIO: Mesmo que a nota seja altíssima, você DEVE propor uma reescrita usando uma abordagem diferente, testando novos formatos ou tons arquiteturais. É PROIBIDO dizer que a instrução atual está perfeita e recusar-se a alterá-la."""
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField(desc="Feedback detalhado do avaliador explicando os motivos da nota.")
    estrategia_mutacao: str = dspy.InputField(desc="Estratégia de mutação a ser aplicada nesta iteração. Siga rigorosamente a diretriz.")
    critica: str = dspy.OutputField(desc="Análise do feedback e proposta de qual nova abordagem testar (proibido dizer que está perfeito).")
    nova_instrucao: str = dspy.OutputField(desc="A nova skill reescrita e otimizada, formatada em Markdown.")

class MutadorCognitivoAgentSignature(dspy.Signature):
    """Analisa a instrução com derivação lógica estruturada obrigatória. OBRIGATÓRIO: preencha
    raciocinio_estruturado com premissas, deduções e conclusão explícitas antes de reescrever.
    A nova instrução DEVE incluir as seções ## Raciocínio, ## Regras, ## Conclusão derivadas do raciocínio."""
    instrucao_anterior: str = dspy.InputField()
    nota_anterior: str = dspy.InputField()
    feedback_juiz: str = dspy.InputField(desc="Feedback detalhado do avaliador explicando os motivos da nota.")
    estrategia_mutacao: str = dspy.InputField(desc="Estratégia de mutação a ser aplicada nesta iteração. Siga rigorosamente a diretriz.")
    critica: str = dspy.OutputField(desc="Análise do feedback e proposta de nova abordagem com derivação cognitiva.")
    raciocinio_estruturado: str = dspy.OutputField(
        desc="Derivação lógica obrigatória com campos: premissas | deducoes | conclusao. Não pode ser genérico."
    )
    nova_instrucao: str = dspy.OutputField(
        desc="A nova skill reescrita em Markdown. DEVE conter ## Raciocínio, ## Regras, ## Conclusão derivados do raciocinio_estruturado."
    )

class MetricsGeneratorSignature(dspy.Signature):
    """
    Gera perguntas especificas de avaliacao para uma instrucao.
    Essas perguntas serao usadas como checklist durante a avaliacao
    para garantir foco em instruction following.
    """
    instruction: str = dspy.InputField(desc="A instrucao para a qual gerar perguntas de avaliacao.")
    regras_adicionais: str = dspy.InputField(desc="Regras adicionais especificadas pelo usuario.")
    pergunta_1: str = dspy.OutputField(desc="Primeira pergunta (mais importante) sobre o que constitui um bom output para esta instrucao.")
    pergunta_2: str = dspy.OutputField(desc="Segunda pergunta sobre o que constitui um bom output para esta instrucao.")
    pergunta_3: str = dspy.OutputField(desc="Terceira pergunta (menos importante) sobre o que constitui um bom output para esta instrucao.")


class SwapSynthesisSignature(dspy.Signature):
    """
    Sintese de preferencias conflitantes do Swap.
    Recebe dois reasonings conflitantes e decide qual e o correto,
    priorizando instruction following sobre estilo.
    """
    instruction: str = dspy.InputField(desc="A instrucao original.")
    output_a: str = dspy.InputField(desc="Output (a).")
    output_b: str = dspy.InputField(desc="Output (b).")
    reasoning_a_better: str = dspy.InputField(desc="Reasoning que defende que Output (a) e melhor.")
    reasoning_b_better: str = dspy.InputField(desc="Reasoning que defende que Output (b) e melhor.")
    decisao_final: str = dspy.OutputField(desc="'Output (a)' ou 'Output (b)' — qual e objetivamente melhor em instruction following.")


class AvaliadorDeSkillSignature(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA é estruturalmente superior à original.
    Analisa 6 dimensões ortogonais: clareza, formatação, robustez, densidade informacional,
    acionabilidade e anti-fragilidade. Todas as regras exigidas devem ser cumpridas.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restrições ou métricas extras especificadas pelo usuário que devem ser estritamente seguidas.")

    manteve_regras_criticas: bool = dspy.OutputField(desc="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    nota_clareza: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a instrução é clara e direta.")
    nota_formatacao: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.")
    nota_robustez: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.")
    nota_densidade_informacional: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando a razão sinal/ruído - penaliza verbosidade vazia e repetição sem valor.")
    nota_acionabilidade: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando se as instruções são claras o suficiente para um agente de IA executar sem ambiguidade.")
    nota_anti_fragilidade: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a skill resiste a edge cases, inputs adversariais e contextos ambíguos.")
    feedback_detalhado: str = dspy.OutputField(desc="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")

class AvaliadorModoBSignature(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA e estruturalmente superior a original.
    Analisa 6 dimensoes: clareza, formatacao, robustez, densidade informacional,
    acionabilidade e anti-fragilidade. Enumere contradicoes e defeitos primeiro.

    REGRAS DE AVALIACAO (OBRIGATORIO seguir):
    (1) PRIORIZE instruction following sobre estilo superficial.
        Um output que executa precisamente a instrucao e SEMPRE melhor
        que um output com tom polido mas que desvia do solicitado.
    (2) Vocabulario pomposo sem substancia DEVE ser penalizado na nota
        de densidade informacional. Palavras como 'axioma', 'decomposicao
        espectral', 'oraculo' sem necessidade tecnica sao ruido, nao qualidade.
    (3) Outputs com MAIS ou MENOS conteudo que o solicitado sao piores,
        independente da qualidade do conteudo extra.
    (4) REGRAS ADICIONAIS SAO CONTRATO INABALAVEL. O campo regras_adicionais
        contem restricoes que DEVEM ser preservadas na skill_otimizada.
        Se a skill_otimizada violar QUALQUER restricao das regras_adicionais,
        manteve_regras_criticas DEVE ser False. Nao ha excecoes nem
        interpretacoes criativas - a violacao e binaria e inegociavel.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restrições ou métricas extras especificadas pelo usuário que devem ser estritamente seguidas.")

    manteve_regras_criticas: bool = dspy.OutputField(desc="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    defeitos_encontrados: list[str] = dspy.OutputField(desc="Lista de violações, paradoxos e ambiguidades detectadas.")
    nota_clareza: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a instrução é clara e direta.")
    nota_formatacao: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.")
    nota_robustez: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.")
    nota_densidade_informacional: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando a razão sinal/ruído - penaliza verbosidade vazia e repetição sem valor.")
    nota_acionabilidade: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando se as instruções são claras o suficiente para um agente de IA executar sem ambiguidade.")
    nota_anti_fragilidade: float = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a skill resiste a edge cases, inputs adversariais e contextos ambíguos.")
    feedback_detalhado: str = dspy.OutputField(desc="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")


# Adapters

class DSPyStrategyDiscoverer(IStrategyDiscoverer):
    def __init__(self):
        self._predictor = dspy.ChainOfThought(StrategyDiscovererSignature)

    def __call__(self, skill_atual: str, feedbacks_recentes: str, estrategias_conhecidas: str) -> DiscoveredStrategy:
        res = self._predictor(
            skill_atual=_sanitize_unicode_for_api(skill_atual),
            feedbacks_recentes=_sanitize_unicode_for_api(feedbacks_recentes),
            estrategias_conhecidas=_sanitize_unicode_for_api(estrategias_conhecidas)
        )
        return DiscoveredStrategy(
            nome_estrategia=res.nome_estrategia,
            prompt_estrategia=res.prompt_estrategia
        )

class DSPySelfReflectiveAgent(ISelfReflectiveAgent):
    def __init__(self):
        self._predictor = dspy.ChainOfThought(SelfReflectiveAgentSignature)
        self._fast_predictor = dspy.Predict(SelfReflectiveAgentSignature)

    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str) -> SelfReflectiveOutput:
        # Sanitização para APIs que não aceitam Unicode (ex: Zhipu/Zai)
        instrucao_anterior = _sanitize_unicode_for_api(instrucao_anterior)
        feedback_juiz = _sanitize_unicode_for_api(feedback_juiz)
        estrategia_mutacao = _sanitize_unicode_for_api(estrategia_mutacao)

        # Uso avançado de módulos: selecionar arquitetura baseada na heurística
        if "direto" in estrategia_mutacao.lower() or "simples" in estrategia_mutacao.lower():
            predictor = self._fast_predictor
        else:
            predictor = self._predictor

        max_retries = 2
        res = None
        current_strategy = estrategia_mutacao
        for attempt in range(max_retries):
            res = predictor(
                instrucao_anterior=instrucao_anterior,
                nota_anterior=nota_anterior,
                feedback_juiz=feedback_juiz,
                estrategia_mutacao=current_strategy
            )
            
            if res.nova_instrucao and res.nova_instrucao.strip() and res.nova_instrucao.strip() != instrucao_anterior.strip():
                break
                
            # Internal Refine: hint aggressively if LLM generated identical output
            current_strategy += "\n[CRÍTICO] A ÚLTIMA RESPOSTA GERADA FOI IDÊNTICA À ORIGINAL. ISSO É INACEITÁVEL. VOCÊ DEVE REESCREVER O TEXTO APLICANDO A MUTAÇÃO!"

        return SelfReflectiveOutput(
            critica=res.critica,
            nova_instrucao=res.nova_instrucao
        )

class DSPyMutadorCognitivoAgent(IMutadorCognitivoAgent):
    def __init__(self):
        self._predictor = dspy.ChainOfThought(MutadorCognitivoAgentSignature)
        self._predict_predictor = dspy.Predict(MutadorCognitivoAgentSignature)

    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str) -> MutadorCognitivoAgentOutput:
        # Sanitização para APIs que não aceitam Unicode (ex: Zhipu/Zai)
        instrucao_anterior = _sanitize_unicode_for_api(instrucao_anterior)
        feedback_juiz = _sanitize_unicode_for_api(feedback_juiz)
        estrategia_mutacao = _sanitize_unicode_for_api(estrategia_mutacao)

        # Se a estratégia já exige raciocínio explícito estruturado, 
        # ChainOfThought pode causar redundância dupla. Podemos usar Predict em heurísticas lógicas.
        if "premissas" in estrategia_mutacao.lower() or "dedução" in estrategia_mutacao.lower():
            predictor = self._predict_predictor
        else:
            predictor = self._predictor

        max_retries = 2
        res = None
        current_strategy = estrategia_mutacao
        for attempt in range(max_retries):
            res = predictor(
                instrucao_anterior=instrucao_anterior,
                nota_anterior=nota_anterior,
                feedback_juiz=feedback_juiz,
                estrategia_mutacao=current_strategy
            )
            
            if res.nova_instrucao and res.nova_instrucao.strip() and res.nova_instrucao.strip() != instrucao_anterior.strip():
                break
                
            current_strategy += "\n[CRÍTICO] A ÚLTIMA RESPOSTA GERADA FOI IDÊNTICA À ORIGINAL. ISSO É INACEITÁVEL. VOCÊ DEVE REESCREVER O TEXTO APLICANDO A MUTAÇÃO!"

        return MutadorCognitivoAgentOutput(
            critica=res.critica,
            raciocinio_estruturado=res.raciocinio_estruturado,
            nova_instrucao=res.nova_instrucao
        )


class DSPyAvaliadorModoB(IAvaliadorModoB):
    def __init__(self, predictor=None):
        self._predictor = predictor or dspy.ChainOfThought(AvaliadorModoBSignature)

    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'

        res = self._predictor(
            skill_original=_sanitize_unicode_for_api(skill_original),
            skill_otimizada=_sanitize_unicode_for_api(skill_otimizada),
            regras_adicionais=_sanitize_unicode_for_api(regras_adicionais)
        )

        return AvaliacaoModoB(
            manteve_regras_criticas=bool(res.manteve_regras_criticas),
            defeitos_encontrados=list(getattr(res, 'defeitos_encontrados', [])),
            nota_clareza=float(res.nota_clareza),
            nota_formatacao=float(res.nota_formatacao),
            nota_robustez=float(res.nota_robustez),
            nota_densidade_informacional=float(res.nota_densidade_informacional),
            nota_acionabilidade=float(res.nota_acionabilidade),
            nota_anti_fragilidade=float(res.nota_anti_fragilidade),
            feedback_detalhado=res.feedback_detalhado
        )

avaliador_modo_b_module = dspy.ChainOfThought(AvaliadorModoBSignature)

def load_avaliador():
    model_path_b = Path('src/outputs/models/avaliador_modo_b_otimizado.json')
    if model_path_b.exists():
        try:
            avaliador_modo_b_module.load(str(model_path_b))
            print(f"[*] Avaliador otimizado Modo B carregado de {model_path_b}.")
        except Exception as e:
            print(f"[!] Erro ao carregar avaliador Modo B: {e}")

# Helpers for drift runner that needs to inject its own predictor
def _invoke_judge_with(module, exemplo, predicao) -> Avaliacao:
    regras = getattr(exemplo, 'regras_adicionais', '')
    if not regras:
        regras = 'Preservar todas as regras comportamentais anteriores.'

    res = module(
        skill_original=exemplo.skill_original,
        skill_otimizada=predicao.skill_otimizada,
        regras_adicionais=regras
    )

    return Avaliacao(
        manteve_regras_criticas=bool(res.manteve_regras_criticas),
        nota_clareza=float(res.nota_clareza),
        nota_formatacao=float(res.nota_formatacao),
        nota_robustez=float(res.nota_robustez),
        nota_densidade_informacional=float(res.nota_densidade_informacional),
        nota_acionabilidade=float(res.nota_acionabilidade),
        nota_anti_fragilidade=float(res.nota_anti_fragilidade),
        feedback_detalhado=res.feedback_detalhado
    )

def _invoke_judge_modo_b_with(module, exemplo, predicao) -> AvaliacaoModoB:
    regras = getattr(exemplo, 'regras_adicionais', '')
    if not regras:
        regras = 'Preservar todas as regras comportamentais anteriores.'

    res = module(
        skill_original=exemplo.skill_original,
        skill_otimizada=predicao.skill_otimizada,
        regras_adicionais=regras
    )

    return AvaliacaoModoB(
        manteve_regras_criticas=bool(res.manteve_regras_criticas),
        defeitos_encontrados=list(getattr(res, 'defeitos_encontrados', [])),
        nota_clareza=float(res.nota_clareza),
        nota_formatacao=float(res.nota_formatacao),
        nota_robustez=float(res.nota_robustez),
        nota_densidade_informacional=float(res.nota_densidade_informacional),
        nota_acionabilidade=float(res.nota_acionabilidade),
        nota_anti_fragilidade=float(res.nota_anti_fragilidade),
        feedback_detalhado=res.feedback_detalhado
    )
