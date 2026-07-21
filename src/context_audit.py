"""
Context Quality Audit — Avaliador de Engenharia de Contexto para Agentes de IA.

Baseado nos 7 critérios empíricos do artigo:
"AI Agents Do Not Fail Alone: The Context Fails First" (Bousetouane, 2026).
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import textstat

textstat.set_lang('pt')


@dataclass
class CriterionScore:
    name: str
    label_pt: str
    score: float  # 0.0 a 10.0
    key_finding: str


@dataclass
class ContextAuditReport:
    overall_score: float  # 0.0 a 10.0
    grade: str  # "Strong" | "Adequate" | "Weak"
    criteria: List[CriterionScore]
    predicted_risks: List[str]
    top_fixes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 1),
            "grade": self.grade,
            "criteria": [
                {
                    "name": c.name,
                    "label_pt": c.label_pt,
                    "score": round(c.score, 1),
                    "key_finding": c.key_finding,
                }
                for c in self.criteria
            ],
            "predicted_risks": self.predicted_risks,
            "top_fixes": self.top_fixes,
        }


# Buzzwords vadias / verbosidade oca
_VAGUE_BUZZWORDS = [
    r"\bdelve\b", r"\btestament\b", r"\bin conclusion\b", r"\bmoreover\b",
    r"\bfurthermore\b", r"\bnevertheless\b", r"\bit(?:'s| is) worth noting\b",
    r"\bin summary\b", r"\bpivotal\b", r"\bseamless(?:ly)?\b", r"\brobust\b",
    r"\bleverage\b", r"\bsynergy\b", r"\bgroundbreaking\b",
    r"\bem suma\b", r"\bem conclusão\b", r"\bcabe ressaltar\b",
    r"\bé importante destacar\b", r"\bno contexto atual\b", r"\bde extrema importância\b",
]
_BUZZWORD_RE = re.compile("|".join(_VAGUE_BUZZWORDS), re.IGNORECASE)


def audit_context_heuristics(skill_text: str) -> ContextAuditReport:
    """
    Realiza a auditoria pré-flight do contexto/skill através dos 7 critérios.
    Funciona via análise estática heurística e estrutural imediata.
    """
    text = skill_text.strip()
    text_lower = text.lower()
    total_len = len(text)
    word_count = textstat.lexicon_count(text)

    # 1. Role Clarity (Clareza de Papel)
    role_score = 5.0
    role_finding = "Definição de papel genérica ou implícita."
    if re.search(r"(?i)#+\s*(papel|função|identity|identidade|você é|role|persona)", text):
        role_score += 3.0
        role_finding = "Seção de identidade/papel explicitamente declarada."
    if "você é" in text_lower or "you are" in text_lower or "atuando como" in text_lower or "act as" in text_lower:
        role_score += 2.0
        if role_score < 10.0:
            role_finding += " (Declaração de persona identificada)."
    role_score = min(10.0, role_score)

    # 2. Guardrail Coverage (Cobertura de Guardrails)
    guard_score = 2.0
    guard_finding = "Sem regras de recusa ou limitações claras de segurança."
    guard_keywords = [
        "não", "nunca", "proibido", "apenas se", "restrição", "limite",
        "never", "do not", "refuse", "guardrail", "atenção", "importante", "warning", "caution", "regras"
    ]
    hits = sum(1 for kw in guard_keywords if kw in text_lower)
    if hits > 0:
        guard_score = min(10.0, 2.0 + hits * 1.25)
        guard_finding = f"Presentes {hits} marcadores de guardrail e restrições comportamentais."

    # 3. Instruction Consistency (Consistência das Instruções)
    cons_score = 7.0
    cons_finding = "Fluxo de instruções estruturado sem contradições óbvias."
    if re.search(r"(?i)(prioridade|ordem de precedência|em caso de conflito|prevalece|hierarquia)", text):
        cons_score += 3.0
        cons_finding = "Possui regras explícitas de hierarquia e resolução de conflito."
    elif total_len < 100:
        cons_score = 4.0
        cons_finding = "Instruções excessivamente breves podem gerar ambiguidade."
    cons_score = min(10.0, cons_score)

    # 4. Tool Schema Quality (Qualidade de Esquema das Ferramentas)
    tool_score = 5.0
    tool_finding = "Não cita ferramentas específicas ou possui especificações genéricas."
    if re.search(r"(?i)(ferramenta|tool|mcp|api|função|parâmetros|schema|json|payload|args|arguments|parameters)", text):
        tool_score = 7.5
        tool_finding = "Declaração de ferramentas/parâmetros presentes."
        if re.search(r"(?i)(string|int|float|boolean|array|object|required|type|esquema)", text):
            tool_score = 9.5
            tool_finding = "Contrato de ferramentas fortemente tipado e parametrizado."

    # 5. Grounding Sufficiency (Suficiência de Fundamentação / RAG / Exemplos)
    ground_score = 3.0
    ground_finding = "Poucos ou nenhuns exemplos/casos de uso fornecidos no contexto."
    if re.search(r"(?i)(exemplo|exem:|[eE]xample|caso de uso|few-shot|demonstração|referência|exemplo de uso|exemplo visual)", text):
        ground_score = 8.5
        ground_finding = "Contém exemplos práticos ou referências diretas de fundamentação."

    # 6. Injection Hardening (Proteção contra Injeção de Prompt / Untrusted Input)
    inj_score = 3.0
    inj_finding = "Entradas de usuário não isoladas das instruções do sistema."
    if re.search(r"(?i)(delimitad|untrusted|<user_input>|<context>|<data>|<input>|tags xml|sanitiz|aspas|backticks|separe|trust boundar)", text_lower):
        inj_score = 9.0
        inj_finding = "Isolamento explícito de inputs não confiáveis e contorno de injeções (tags XML/delimitadores)."

    # 7. Token Efficiency (Eficiência de Tokens e Sinal-Ruído)
    tok_score = 8.0
    tok_finding = "Boa densidade semântica e pouca verbosidade oca."
    buzzwords_found = len(_BUZZWORD_RE.findall(text))
    if buzzwords_found > 2:
        tok_score = max(2.0, 8.0 - buzzwords_found * 1.5)
        tok_finding = f"Presença de {buzzwords_found} clichês/buzzwords de escrita oca de IA."
    elif word_count > 1000:
        tok_score = 6.0
        tok_finding = "Texto muito longo; considere modularizar em sub-skills."

    criteria = [
        CriterionScore("role_clarity", "Clareza de Papel", role_score, role_finding),
        CriterionScore("guardrail_coverage", "Cobertura de Guardrails", guard_score, guard_finding),
        CriterionScore("instruction_consistency", "Consistência de Instruções", cons_score, cons_finding),
        CriterionScore("tool_schema_quality", "Contrato de Ferramentas", tool_score, tool_finding),
        CriterionScore("grounding_sufficiency", "Fundamentação (Exemplos/RAG)", ground_score, ground_finding),
        CriterionScore("injection_hardening", "Proteção contra Injeção", inj_score, inj_finding),
        CriterionScore("token_efficiency", "Eficiência de Tokens", tok_score, tok_finding),
    ]

    overall = sum(c.score for c in criteria) / len(criteria)

    if overall >= 8.0:
        grade = "Strong"
    elif overall >= 5.0:
        grade = "Adequate"
    else:
        grade = "Weak"

    # Mapeamento dos riscos previstos (com base nos critérios de menor nota)
    risks = []
    sorted_criteria = sorted(criteria, key=lambda c: c.score)
    lowest_2 = sorted_criteria[:2]

    risk_map = {
        "role_clarity": "Risco de desvio de escopo (Instruction Drift) e incerteza operacional.",
        "guardrail_coverage": "Risco de respostas inadequadas, quebra de limites e alucinações de segurança.",
        "instruction_consistency": "Risco de comportamentos contraditórios sob cenários de contorno.",
        "tool_schema_quality": "Risco de chamadas incorretas ou malformadas de ferramentas (Tool Misuse).",
        "grounding_sufficiency": "Risco elevado de alucinação factual por falta de referências concretas.",
        "injection_hardening": "Vulnerabilidade a injeções de prompt e manipulação por inputs do usuário.",
        "token_efficiency": "Desperdício de orçamento de tokens e diluição de atenção em modelos de contexto longo.",
    }

    for c in lowest_2:
        if c.score < 7.0 and c.name in risk_map:
            risks.append(risk_map[c.name])

    if not risks:
        risks.append("Nenhum risco crítico imediato detectado no contexto fornecido.")

    # Top 3 correções de maior alavancagem
    top_fixes = []
    for c in sorted_criteria[:3]:
        if c.name == "guardrail_coverage":
            top_fixes.append("Adicione seções explícitas de restrições ('O que NÃO fazer') e regras de recusa.")
        elif c.name == "injection_hardening":
            top_fixes.append("Delimite inputs do usuário utilizando tags XML ou marcadores estritos de contorno.")
        elif c.name == "grounding_sufficiency":
            top_fixes.append("Inclua exemplos de poucos disparos (few-shot) ou esquema explícito de dados.")
        elif c.name == "role_clarity":
            top_fixes.append("Defina claramente o papel do agente, objetivo central e limites de atuação.")
        elif c.name == "instruction_consistency":
            top_fixes.append("Especifique regras explícitas de precedência em caso de ambiguidades ou conflitos.")
        elif c.name == "token_efficiency":
            top_fixes.append("Remova clichês de IA e frases de preenchimento para aumentar a densidade de informação.")
        elif c.name == "tool_schema_quality":
            top_fixes.append("Documente os parâmetros esperados e os retornos das ferramentas de forma tipada.")

    return ContextAuditReport(
        overall_score=overall,
        grade=grade,
        criteria=criteria,
        predicted_risks=risks,
        top_fixes=top_fixes[:3],
    )
