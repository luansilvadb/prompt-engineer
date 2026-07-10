import dspy
from pathlib import Path
from src.signatures import Avaliacao, AvaliacaoModoB
from src.domain.agent_interfaces import (
    EstrategiaDescoberta,
    SelfReflectiveOutput,
    MutadorCognitivoAgentOutput,
    IStrategyDiscoverer,
    ISelfReflectiveAgent,
    IMutadorCognitivoAgent,
    IAvaliadorModoB,
    IAvaliadorDeSkill
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

class AvaliadorDeSkillSignature(dspy.Signature):
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

class AvaliadorModoBSignature(dspy.Signature):
    """
    Avalia se uma skill otimizada para agentes de IA é estruturalmente superior à original (Modo B - Caça-Defeitos).
    Analisa as mesmas 6 dimensões, mas obrigatoriamente enumera contradições e defeitos primeiro.
    """
    skill_original: str = dspy.InputField()
    skill_otimizada: str = dspy.InputField()
    regras_adicionais: str = dspy.InputField(desc="Diretrizes, restrições ou métricas extras especificadas pelo usuário que devem ser estritamente seguidas.")
    
    manteve_regras_criticas: str = dspy.OutputField(desc="True se nenhuma regra comportamental vital (inclusive as regras adicionais) foi omitida. False caso contrário.")
    defeitos_encontrados: str = dspy.OutputField(desc="Lista de violações, paradoxos e ambiguidades detectadas. Enumere cada defeito encontrado (use nova linha para cada).")
    nota_clareza: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a instrução é clara e direta.")
    nota_formatacao: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando o uso de markdown, listas e negritos.")
    nota_robustez: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando a imunidade a 'lost in the middle' e ambiguidades.")
    nota_densidade_informacional: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando a razão sinal/ruído — penaliza verbosidade vazia e repetição sem valor.")
    nota_acionabilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se as instruções são claras o suficiente para um agente de IA executar sem ambiguidade.")
    nota_anti_fragilidade: str = dspy.OutputField(desc="Nota de 0 a 100 avaliando se a skill resiste a edge cases, inputs adversariais e contextos ambíguos.")
    feedback_detalhado: str = dspy.OutputField(desc="Explicação detalhada dos pontos fortes e fracos, justificando as notas.")


# Adapters

class DSPyStrategyDiscoverer(IStrategyDiscoverer):
    def __init__(self):
        self._predictor = dspy.Predict(StrategyDiscovererSignature)

    def __call__(self, skill_atual: str, feedbacks_recentes: str, estrategias_conhecidas: str) -> EstrategiaDescoberta:
        res = self._predictor(
            skill_atual=skill_atual,
            feedbacks_recentes=feedbacks_recentes,
            estrategias_conhecidas=estrategias_conhecidas
        )
        return EstrategiaDescoberta(
            nome_estrategia=res.nome_estrategia,
            prompt_estrategia=res.prompt_estrategia
        )

class DSPySelfReflectiveAgent(ISelfReflectiveAgent):
    def __init__(self):
        self._predictor = dspy.ChainOfThought(SelfReflectiveAgentSignature)

    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str) -> SelfReflectiveOutput:
        res = self._predictor(
            instrucao_anterior=instrucao_anterior,
            nota_anterior=nota_anterior,
            feedback_juiz=feedback_juiz,
            estrategia_mutacao=estrategia_mutacao
        )
        return SelfReflectiveOutput(
            critica=res.critica,
            nova_instrucao=res.nova_instrucao
        )

class DSPyMutadorCognitivoAgent(IMutadorCognitivoAgent):
    input_fields = MutadorCognitivoAgentSignature.input_fields
    output_fields = MutadorCognitivoAgentSignature.output_fields

    def __init__(self):
        self._predictor = dspy.ChainOfThought(MutadorCognitivoAgentSignature)

    def __call__(self, instrucao_anterior: str, nota_anterior: str, feedback_juiz: str, estrategia_mutacao: str) -> MutadorCognitivoAgentOutput:
        res = self._predictor(
            instrucao_anterior=instrucao_anterior,
            nota_anterior=nota_anterior,
            feedback_juiz=feedback_juiz,
            estrategia_mutacao=estrategia_mutacao
        )
        return MutadorCognitivoAgentOutput(
            critica=res.critica,
            raciocinio_estruturado=res.raciocinio_estruturado,
            nova_instrucao=res.nova_instrucao
        )

def _parse_manteve_regras(manteve_str: str) -> bool:
    manteve_str = str(manteve_str).strip().lower()
    return 'true' in manteve_str or 'sim' in manteve_str or 'yes' in manteve_str or manteve_str == '1'



class DSPyAvaliadorModoB(IAvaliadorModoB):
    def __init__(self, predictor=None):
        self._predictor = predictor or dspy.Predict(AvaliadorModoBSignature)

    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'
            
        res = self._predictor(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais
        )
        
        defeitos_raw = getattr(res, 'defeitos_encontrados', '')
        if isinstance(defeitos_raw, str):
            defeitos_list = [d.strip("- *").strip() for d in defeitos_raw.split('\\n') if d.strip("- *").strip()]
        elif isinstance(defeitos_raw, list):
            defeitos_list = [str(d) for d in defeitos_raw]
        else:
            defeitos_list = []
            
        return AvaliacaoModoB(
            manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
            defeitos_encontrados=defeitos_list,
            nota_clareza=res.nota_clareza,
            nota_formatacao=res.nota_formatacao,
            nota_robustez=res.nota_robustez,
            nota_densidade_informacional=res.nota_densidade_informacional,
            nota_acionabilidade=res.nota_acionabilidade,
            nota_anti_fragilidade=res.nota_anti_fragilidade,
            feedback_detalhado=res.feedback_detalhado
        )

# Global instances for teleprompter and backward-compatibility with services that just load
avaliador_module = dspy.Predict(AvaliadorDeSkillSignature)
avaliador_modo_b_module = dspy.Predict(AvaliadorModoBSignature)

def load_avaliador():
    model_path_a = Path('src/outputs/models/avaliador_modo_a_otimizado.json')
    if model_path_a.exists():
        try:
            avaliador_module.load(str(model_path_a))
            print(f"[*] Avaliador otimizado Modo A carregado de {model_path_a}.")
        except Exception as e:
            print(f"[!] Erro ao carregar avaliador Modo A: {e}")
            
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
        manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
        nota_clareza=res.nota_clareza,
        nota_formatacao=res.nota_formatacao,
        nota_robustez=res.nota_robustez,
        nota_densidade_informacional=res.nota_densidade_informacional,
        nota_acionabilidade=res.nota_acionabilidade,
        nota_anti_fragilidade=res.nota_anti_fragilidade,
        feedback_detalhado=res.feedback_detalhado
    )

from src.domain.agent_interfaces import IProbeJudge, IProbeJudgeModoB, JudgeRegistry

class DSPyProbeJudge(IProbeJudge):
    def __init__(self):
        self._predictor = dspy.Predict(AvaliadorDeSkillSignature)

    def load(self, path: str) -> None:
        self._predictor.load(path)

    def as_zero(self) -> None:
        self._predictor = dspy.Predict(AvaliadorDeSkillSignature)

    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> Avaliacao:
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'
        res = self._predictor(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais
        )
        return Avaliacao(
            manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
            nota_clareza=res.nota_clareza,
            nota_formatacao=res.nota_formatacao,
            nota_robustez=res.nota_robustez,
            nota_densidade_informacional=res.nota_densidade_informacional,
            nota_acionabilidade=res.nota_acionabilidade,
            nota_anti_fragilidade=res.nota_anti_fragilidade,
            feedback_detalhado=res.feedback_detalhado
        )

class DSPyProbeJudgeModoB(IProbeJudgeModoB):
    def __init__(self):
        self._predictor = dspy.Predict(AvaliadorModoBSignature)

    def load(self, path: str) -> None:
        self._predictor.load(path)

    def as_zero(self) -> None:
        self._predictor = dspy.Predict(AvaliadorModoBSignature)

    def __call__(self, skill_original: str, skill_otimizada: str, regras_adicionais: str) -> AvaliacaoModoB:
        if not regras_adicionais:
            regras_adicionais = 'Preservar todas as regras comportamentais anteriores.'
        res = self._predictor(
            skill_original=skill_original,
            skill_otimizada=skill_otimizada,
            regras_adicionais=regras_adicionais
        )
        
        defeitos_raw = getattr(res, 'defeitos_encontrados', '')
        if isinstance(defeitos_raw, str):
            defeitos_list = [d.strip("- *").strip() for d in defeitos_raw.split('\\n') if d.strip("- *").strip()]
        elif isinstance(defeitos_raw, list):
            defeitos_list = [str(d) for d in defeitos_raw]
        else:
            defeitos_list = []

        return AvaliacaoModoB(
            manteve_regras_criticas=_parse_manteve_regras(res.manteve_regras_criticas),
            defeitos_encontrados=defeitos_list,
            nota_clareza=res.nota_clareza,
            nota_formatacao=res.nota_formatacao,
            nota_robustez=res.nota_robustez,
            nota_densidade_informacional=res.nota_densidade_informacional,
            nota_acionabilidade=res.nota_acionabilidade,
            nota_anti_fragilidade=res.nota_anti_fragilidade,
            feedback_detalhado=res.feedback_detalhado
        )

# Register with JudgeRegistry
JudgeRegistry.register(DSPyProbeJudge, DSPyProbeJudgeModoB)
JudgeRegistry.register_signature_modo_b(AvaliadorModoBSignature)
