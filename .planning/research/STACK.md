# Stack Research

**Domain:** LLM Reasoning Optimization (Mutador Cognitivo e Avaliador de Profundidade)
**Researched:** 2026-07-10
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `pydantic` | `^2.7.0` | Extração e Validação Estrutural | Para o Mutador Cognitivo injetar protocolos rigorosos (ex: `<Pensamento>`, `<Crítica>`, `<Plano>`), precisamos forçar saídas estruturadas. Pydantic integra nativamente com `dspy.Output` (ou LiteLLM) garantindo que o Avaliador possa ler campos específicos ao invés de usar Regex em blocos de texto amorfos. |
| `sentence-transformers` | `^3.0.0` | Avaliação de Similaridade Semântica | Essencial para o Avaliador de Profundidade. Penaliza raciocínio raso calculando a distância de cosseno entre a "resposta" e o "prompt" original. Respostas que apenas parafraseiam o prompt terão alta similaridade e sofrerão penalidade matemática no MCTS. |
| `textstat` | `^0.7.3` | Heurísticas de Profundidade Textual | Fornece métricas de complexidade léxica e de leitura (ex: Flesch-Kincaid). É uma verificação em tempo real, ultraleve (sem custo de LLM), ideal para podar (prune) nós do MCTS onde o raciocínio gerado possui baixa entropia ou complexidade rasteira. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `numpy` | `^1.26.0` | Operações Vetoriais | Necessário para calcular a similaridade de cosseno de forma performática quando usar `sentence-transformers` no pipeline do Juiz. |
| `jinja2` | `^3.1.3` | Templating de Prompts Cognitivos | Útil caso o Mutador Cognitivo precise orquestrar traces complexos de raciocínio dinâmico e injetar variáveis de histórico (experiências passadas) antes de enviar ao DSPy. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest-asyncio` | Testes de pipelines assíncronos | Essencial para testar o Avaliador de Profundidade simulando chamadas LLM e processamento vetorial não-bloqueante. |

## Installation

```bash
# Core
pip install pydantic sentence-transformers textstat

# Supporting
pip install numpy jinja2

# Dev dependencies
pip install pytest-asyncio
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `textstat` | `spaCy` ou `NLTK` | Use `spaCy` apenas se heurísticas simples falharem e houver necessidade de análise de árvore de dependência sintática para detectar falácias lógicas profundas independentes do LLM. (Evitado por padrão por ser muito pesado). |
| Custom DSPy/LiteLLM Judge | `ragas` ou `truera` | Use `ragas` (métricas de *faithfulness* / *answer relevance*) se o pipeline evoluir para RAG completo. Atualmente, expandir o "Juiz Modo B" customizado integrado ao MCTS é mais coeso com a arquitetura existente. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `langchain` / `llama-index` | Cria uma camada extra de abstração desnecessária (bloat). O projeto já utiliza MCTS nativo com DSPy. Agentes do LangChain causariam conflito arquitetural. | `dspy` + `pydantic` nativo |
| Modelos Locais (ex: vLLM) para o Juiz | Sobrecarga de infraestrutura apenas para avaliar profundidade. O gargalo computacional paralisaria as rolagens do MCTS. | Chamadas rápidas a modelos menores/API via LiteLLM combinados com heurísticas vetoriais/lexicais. |

## Stack Patterns by Variant

**If estruturando passos rígidos de raciocínio (Chain-of-Thought determinístico):**
- Use `pydantic` schemas atrelados a classes do DSPy.
- Because garante parsing sem falhas no backpropagation da árvore MCTS.

**If detectando paráfrase e "preguiça cognitiva" do LLM:**
- Use `sentence-transformers` (modelo leve, ex: `all-MiniLM-L6-v2`) para aplicar *cosine penalty*.
- Because um LLM juiz pode se deixar enganar pela estética, enquanto um embedding focado em similaridade denunciará a repetição de conteúdo instantaneamente.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `pydantic@2.7+` | `dspy-ai@latest` | Garantir que o DSPy suporte as assinaturas tipadas modernas (Pydantic v2). Algumas versões mais antigas do DSPy requeriam Pydantic v1. |

## Sources

- DSPy Documentation — Typed Predictors and Assertions
- Pydantic Documentation — Structured LLM outputs
- Sentence-Transformers Docs — Cosine Similarity for Text Penalization

---
*Stack research for: LLM Reasoning Optimization (Mutador Cognitivo e Avaliador de Profundidade)*
*Researched: 2026-07-10*
