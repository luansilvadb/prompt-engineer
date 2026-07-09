# Phase 1 Context: Architectural Cleanup & Densification

## Domain
Limpeza estrutural da base de código, remoção de código morto e redução de complexidade de funções, focando na sustentabilidade sem alterar a lógica core.

## Canonical Refs
- [.planning/ROADMAP.md](../../ROADMAP.md)
- [.planning/REQUIREMENTS.md](../../REQUIREMENTS.md)
- [.planning/PROJECT.md](../../PROJECT.md)
- [.planning/codebase/ARCHITECTURE.md](../../codebase/ARCHITECTURE.md)
- [.planning/codebase/CONCERNS.md](../../codebase/CONCERNS.md)

## Decisions
- **Reorganização de Módulos (Densification):** Criar subpastas lógicas (ex: `src/drift/`) contendo vários arquivos pequenos, separando bem as responsabilidades.
- **Estratégia de Complexidade Ciclomática:** Usar funções auxiliares simples e funcionais, focando apenas na redução da complexidade de leitura do código. Evitar "overengineering" com Padrões de Projeto complexos (como OO Strategy).
- **Tratamento de Código Morto:** Apagar código não utilizado (funções, variáveis, imports) imediatamente para limpar a base. Utilizar o Git para recuperação, se necessário.

## Prior Context
*Nenhum.*

## Code Context
- Monolithic API server with FastAPI.
- Persistência baseada em File System (`outputs/`).
- MCTS (Monte Carlo Tree Search) prompt optimizer, e módulo de verificação (DriftGate).
