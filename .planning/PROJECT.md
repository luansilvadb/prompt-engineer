# Skill Optimizer

## What This Is

Um servidor de API FastAPI especializado em otimização de prompts (Teleprompter) usando LiteLLM e DSPy. O sistema aplica heurísticas de busca em árvore de Monte Carlo (MCTS) para criar variações de skills e as avalia utilizando um juiz contra um golden set para evitar regressões comportamentais (drift).

## Core Value

Otimização de prompts guiada por MCTS com um mecanismo de avaliação que efetivamente valide o *comportamento* da skill otimizada de forma rigorosa, e não apenas sua estética, garantindo código sustentável e modular.

## Requirements

### Validated

- ✓ Integração com LLMs usando DSPy e LiteLLM (suporte multi-provider).
- ✓ Otimizador de prompts baseado em MCTS.
- ✓ Validação de resultados usando Golden Set para evitar o chamado "drift".
- ✓ API FastAPI para disparar jobs e servir o frontend.
- ✓ **Modo "Caça-Defeitos" do Juiz:** O juiz deve procurar por contradições e falhas na skill (avaliar o comportamento) *antes* de elogiar sua estética. (Validated in v1.0)
- ✓ **Redução de Complexidade Ciclomática:** Refatorar funções com múltiplos branches e caminhos aninhados em unidades menores. (Validated in v1.0)
- ✓ **Remoção de Código Morto:** Eliminar variáveis, funções e imports que não agregam valor. (Validated in v1.0)
- ✓ **Densificação do Projeto:** Arquivos e módulos devem ter escopo e responsabilidades bem delineadas. (Validated in v1.0)

### Active

(None yet — planning next milestone)

### Out of Scope

- Modificação da lógica core do MCTS — o objetivo não é mudar como a busca funciona, mas como o projeto está estruturado e como o juiz atua.
- Quebra de Contratos da API — clientes que usam os endpoints atuais devem continuar funcionando sem alterações.

## Context

A base de código atual funciona bem, mas acumulou complexidade e código morto (brownfield). Além disso, testes manuais revelaram que o "AvaliadorDeSkill" atua como um "crítico de arte" focado na estética do texto e ignora contradições óbvias de comportamento, dando notas altas (0.96) para skills disfuncionais. A introdução de um "Modo B" (caça-defeitos) corrigiu a nota para 0.665. Esta refatoração combinará limpeza profunda com a aplicação definitiva desse novo comportamento do juiz.

Com o v1.0 completo, a base de código (esp. `src/drift/` e `src/mutation_strategies/`) foi limpa e densificada. O Avaliador Modo B está integrado e funcional, avaliando rigidamente as violações de regras estruturais e penalizando a pontuação no MCTS.

## Constraints

- **Tolerância a regressões:** A reestruturação de arquivos e limpeza de código não pode quebrar os algoritmos de mutação nem o pipeline de avaliação que já existem.
- **Isolamento de Estado:** A persistência em `outputs/` baseada em JSON e JSONL deve ser mantida, embora a lógica possa ser simplificada.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Implementar o Juiz em Modo B (Caça-Defeitos) | O modo A atual aprova ambiguidades e contradições comportamentais baseado na beleza do texto. | ✓ Good (Validated in v1.0) |
| Refatoração Restrita aos Internals | Garantir que a API mantenha os mesmos contratos evita quebrar o ecossistema externo ou UIs que dependem dela. | ✓ Good |
| Criar subpacotes `src/drift/` e `src/mutation_strategies/` | Simplifica arquivos inchados e permite separar responsabilidades com clareza. | ✓ Good |

---
*Last updated: 2026-07-10 after v1.0 milestone*
