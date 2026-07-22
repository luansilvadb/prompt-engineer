"""Buzzwords e clichês de IA — fonte única de verdade para todos os módulos de avaliação.

Consolidado de:
  - src/context_audit.py  (18 padrões regex, inglês + pt-BR)
  - src/evaluators/heuristic.py (28 padrões regex, inglês + pt-BR)
  - src/drift/metrics.py   (23 strings literais, pt-BR estilo pomposo)
"""

import re

# ── Vague Buzzwords (regex patterns) ───────────────────────────────────────
# Padrões de verbosidade oca em outputs de LLM. Cada entrada é um padrão regex
# compilável com re.compile(..., re.IGNORECASE).

VAGUE_BUZZWORD_PATTERNS: list[str] = [
    # Inglês — marcadores de texto AI genérico
    r"\bdelve\b", r"\btestament\b", r"\bin conclusion\b", r"\bmoreover\b",
    r"\bfurthermore\b", r"\bnevertheless\b", r"\bit(?:'s| is) worth noting\b",
    r"\bit(?:'s| is) important to note\b", r"\bin summary\b", r"\bin essence\b",
    r"\bto summarize\b", r"\bpivotal\b", r"\blandscape\b", r"\bparadigm\b",
    r"\bseamless(?:ly)?\b", r"\brobust\b", r"\bleverage\b", r"\bsynergy\b",
    r"\bgroundbreaking\b", r"\bstate-of-the-art\b", r"\bcutting-edge\b",
    # Português — equivalentes de verbosidade oca
    r"\bem suma\b", r"\bem conclusão\b", r"\bcabe ressaltar\b",
    r"\bé importante destacar\b", r"\bé fundamental ressaltar\b",
    r"\bno contexto atual\b", r"\bno cenário atual\b",
    r"\bde extrema importância\b", r"\bvalioso\b",
]

VAGUE_BUZZWORD_RE = re.compile("|".join(VAGUE_BUZZWORD_PATTERNS), re.IGNORECASE)

# ── Style Buzzwords (literal strings) ──────────────────────────────────────
# Palavras pomposas em pt-BR usadas para detecção de viés estético no drift.
# Uso: verificação de substring (bw in text.lower()).

STYLE_BUZZWORDS: list[str] = [
    'axioma', 'ontológico', 'ontologica', 'espectral', 'oráculo', 'oraculo',
    'decomposição', 'decomposicao', 'transmutação', 'transmutacao',
    'exegese', 'catarse', 'gênese', 'genese', 'primária', 'primaria',
    'epistemológica', 'epistemologica', 'existencial', 'entropia',
    'cognitiva', 'cognitivo', 'arquitetura ontológica', 'arquitetura ontologica',
    'dogma', 'falácia', 'falacia', 'capitulação', 'capitulacao',
    'paradigma', 'transcendência', 'transcendencia',
]

STYLE_BUZZWORDS_LOWER = [w.lower() for w in STYLE_BUZZWORDS]
