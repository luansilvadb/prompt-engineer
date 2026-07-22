"""
Context Quality Audit — Avaliador de Engenharia de Contexto para Agentes de IA.

Baseado nos 7 critérios empíricos do artigo:
"AI Agents Do Not Fail Alone: The Context Fails First" (Bousetouane, 2026).
"""

import re
from dataclasses import dataclass
from typing import Dict, Any, List, Callable
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


# ── critério #1: Role Clarity ───────────────────────────────────────────────

def _eval_role_clarity(text: str, text_lower: str) -> CriterionScore:
    score = 5.0
    finding = "Definição de papel genérica ou implícita."
    if re.search(r"(?i)#+\s*(papel|função|identity|identidade|você é|role|persona)", text):
        score += 3.0
        finding = "Seção de identidade/papel explicitamente declarada."
    if "você é" in text_lower or "you are" in text_lower or "atuando como" in text_lower or "act as" in text_lower:
        score = min(10.0, score + 2.0)
        if score < 10.0:
            finding += " (Declaração de persona identificada)."
    return CriterionScore("role_clarity", "Clareza de Papel", min(10.0, score), finding)


# ── critério #2: Guardrail Coverage ──────────────────────────────────────────

_GUARD_KEYWORDS = [
    "não", "nunca", "proibido", "apenas se", "restrição", "limite",
    "never", "do not", "refuse", "guardrail", "atenção", "importante",
    "warning", "caution", "regras",
]

def _eval_guardrail_coverage(text_lower: str) -> CriterionScore:
    score = 2.0
    finding = "Sem regras de recusa ou limitações claras de segurança."
    hits = sum(1 for kw in _GUARD_KEYWORDS if kw in text_lower)
    if hits > 0:
        score = min(10.0, 2.0 + hits * 1.25)
        finding = f"Presentes {hits} marcadores de guardrail e restrições comportamentais."
    return CriterionScore("guardrail_coverage", "Cobertura de Guardrails", score, finding)


# ── critério #3: Instruction Consistency ─────────────────────────────────────

def _eval_instruction_consistency(text: str, text_lower: str, total_len: int) -> CriterionScore:
    score = 7.0
    finding = "Fluxo de instruções estruturado sem contradições óbvias."
    if re.search(r"(?i)(prioridade|ordem de precedência|em caso de conflito|prevalece|hierarquia)", text):
        score = min(10.0, score + 3.0)
        finding = "Possui regras explícitas de hierarquia e resolução de conflito."
    elif total_len < 100:
        score = 4.0
        finding = "Instruções excessivamente breves podem gerar ambiguidade."
    return CriterionScore("instruction_consistency", "Consistência de Instruções", min(10.0, score), finding)


# ── critério #4: Tool Schema Quality ─────────────────────────────────────────

def _eval_tool_schema(text: str, text_lower: str) -> CriterionScore:
    score = 5.0
    finding = "Não cita ferramentas específicas ou possui especificações genéricas."
    if re.search(r"(?i)(ferramenta|tool|mcp|api|função|parâmetros|schema|json|payload|args|arguments|parameters)", text):
        score = 7.5
        finding = "Declaração de ferramentas/parâmetros presentes."
        if re.search(r"(?i)(string|int|float|boolean|array|object|required|type|esquema)", text):
            score = 9.5
            finding = "Contrato de ferramentas fortemente tipado e parametrizado."
    return CriterionScore("tool_schema_quality", "Contrato de Ferramentas", score, finding)


# ── critério #5: Grounding Sufficiency ───────────────────────────────────────

def _eval_grounding(text: str, text_lower: str) -> CriterionScore:
    score = 3.0
    finding = "Poucos ou nenhuns exemplos/casos de uso fornecidos no contexto."
    if re.search(r"(?i)(exemplo|exem:|[eE]xample|caso de uso|few-shot|demonstração|referência|exemplo de uso|exemplo visual)", text):
        score = 8.5
        finding = "Contém exemplos práticos ou referências diretas de fundamentação."
    return CriterionScore("grounding_sufficiency", "Fundamentação (Exemplos/RAG)", score, finding)


# ── critério #6: Injection Hardening ─────────────────────────────────────────

_INJECTION_RE = re.compile(
    r"(?i)(delimitad|untrusted|<user_input>|<context>|<data>|<input>|"
    r"tags xml|sanitiz|aspas|backticks|separe|trust boundar)"
)

def _eval_injection_hardening(text_lower: str) -> CriterionScore:
    score = 3.0
    finding = "Entradas de usuário não isoladas das instruções do sistema."
    if _INJECTION_RE.search(text_lower):
        score = 9.0
        finding = "Isolamento explícito de inputs não confiáveis e contorno de injeções (tags XML/delimitadores)."
    return CriterionScore("injection_hardening", "Proteção contra Injeção", score, finding)


# ── critério #7: Token Efficiency ────────────────────────────────────────────

def _eval_token_efficiency(text: str, text_lower: str, word_count: int) -> CriterionScore:
    score = 8.0
    finding = "Boa densidade semântica e pouca verbosidade oca."
    buzzwords_found = len(_BUZZWORD_RE.findall(text))
    if buzzwords_found > 2:
        score = max(2.0, 8.0 - buzzwords_found * 1.5)
        finding = f"Presença de {buzzwords_found} clichês/buzzwords de escrita oca de IA."
    elif word_count > 1000:
        score = 6.0
        finding = "Texto muito longo; considere modularizar em sub-skills."
    return CriterionScore("token_efficiency", "Eficiência de Tokens", score, finding)


# ── risk & fix mappers ───────────────────────────────────────────────────────

_RISK_MAP = {
    "role_clarity": "Risco de desvio de escopo (Instruction Drift) e incerteza operacional.",
    "guardrail_coverage": "Risco de respostas inadequadas, quebra de limites e alucinações de segurança.",
    "instruction_consistency": "Risco de comportamentos contraditórios sob cenários de contorno.",
    "tool_schema_quality": "Risco de chamadas incorretas ou malformadas de ferramentas (Tool Misuse).",
    "grounding_sufficiency": "Risco elevado de alucinação factual por falta de referências concretas.",
    "injection_hardening": "Vulnerabilidade a injeções de prompt e manipulação por inputs do usuário.",
    "token_efficiency": "Desperdício de orçamento de tokens e diluição de atenção em modelos de contexto longo.",
}

_FIX_MAP = {
    "guardrail_coverage": "Adicione seções explícitas de restrições ('O que NÃO fazer') e regras de recusa.",
    "injection_hardening": "Delimite inputs do usuário utilizando tags XML ou marcadores estritos de contorno.",
    "grounding_sufficiency": "Inclua exemplos de poucos disparos (few-shot) ou esquema explícito de dados.",
    "role_clarity": "Defina claramente o papel do agente, objetivo central e limites de atuação.",
    "instruction_consistency": "Especifique regras explícitas de precedência em caso de ambiguidades ou conflitos.",
    "token_efficiency": "Remova clichês de IA e frases de preenchimento para aumentar a densidade de informação.",
    "tool_schema_quality": "Documente os parâmetros esperados e os retornos das ferramentas de forma tipada.",
}


def _compute_risks(criteria: List[CriterionScore]) -> List[str]:
    """Extrai riscos previstos dos 2 critérios com menor nota."""
    lowest_2 = sorted(criteria, key=lambda c: c.score)[:2]
    risks = [_RISK_MAP[c.name] for c in lowest_2 if c.score < 7.0 and c.name in _RISK_MAP]
    return risks or ["Nenhum risco crítico imediato detectado no contexto fornecido."]


def _compute_fixes(criteria: List[CriterionScore]) -> List[str]:
    """Gera top-3 correções a partir dos critérios de menor nota."""
    fixes = []
    for c in sorted(criteria, key=lambda c: c.score)[:3]:
        if c.name in _FIX_MAP:
            fixes.append(_FIX_MAP[c.name])
    return fixes[:3]


def _compute_grade(overall: float) -> str:
    if overall >= 8.0:
        return "Strong"
    if overall >= 5.0:
        return "Adequate"
    return "Weak"


# ── entry point ──────────────────────────────────────────────────────────────

def audit_context_heuristics(skill_text: str) -> ContextAuditReport:
    """
    Realiza a auditoria pré-flight do contexto/skill através dos 7 critérios.
    Funciona via análise estática heurística e estrutural imediata.
    """
    text = skill_text.strip()
    text_lower = text.lower()
    total_len = len(text)
    word_count = textstat.lexicon_count(text)

    evaluators: List[Callable] = [
        _eval_role_clarity,
        _eval_guardrail_coverage,
        _eval_instruction_consistency,
        _eval_tool_schema,
        _eval_grounding,
        _eval_injection_hardening,
        _eval_token_efficiency,
    ]

    criteria: List[CriterionScore] = []
    for ev in evaluators:
        # Pass only the arguments each evaluator actually needs (by name)
        sig = ev.__code__.co_varnames[:ev.__code__.co_argcount]
        kwargs = {}
        for param in sig:
            if param == 'text':
                kwargs[param] = text
            elif param == 'text_lower':
                kwargs[param] = text_lower
            elif param == 'total_len':
                kwargs[param] = total_len
            elif param == 'word_count':
                kwargs[param] = word_count
        criteria.append(ev(**kwargs))

    overall = sum(c.score for c in criteria) / len(criteria)

    return ContextAuditReport(
        overall_score=overall,
        grade=_compute_grade(overall),
        criteria=criteria,
        predicted_risks=_compute_risks(criteria),
        top_fixes=_compute_fixes(criteria),
    )
