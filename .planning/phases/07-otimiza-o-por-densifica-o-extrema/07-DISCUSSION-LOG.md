# Phase 07: Otimização por Densificação Extrema - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 07-Otimização por Densificação Extrema
**Areas discussed:** Fórmula da Recompensa, Métrica de Densidade, Ponto de Integração no Pipeline, Escopo de Aplicação

---

## Fórmula da Recompensa

| Option | Description | Selected |
|--------|-------------|----------|
| Multiplicador final | Densidade multiplica a pontuação final | ✓ |
| Dimensão separada | Densidade como dimensão independente combinada via média ponderada | |
| Bônus aditivo | Bônus fixo ou escalonado adicionado à pontuação | |

**User's choice:** Multiplicador final (após recomendação do agente)
**Notes:** Usuário solicitou recomendação do agente (3x). Agente recomendou multiplicador final. Usuário confirmou. Parâmetros em config.py.

## Métrica de Densidade

| Option | Description | Selected |
|--------|-------------|----------|
| Compressão universal + bônus estruturado | Taxa de compressão (todas estratégias) + bônus para campos estruturados do MutadorCognitivo | ✓ |
| Só compressão | Apenas taxa de compressão | |
| Só campos estruturados | Apenas presença/qualidade dos campos do MutadorCognitivo | |

**User's choice:** Compressão universal + bônus estruturado (após recomendação do agente)
**Notes:** Usuário solicitou recomendação do agente (2x). Agente recomendou abordagem composta. Usuário confirmou.

## Ponto de Integração no Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| Final, após ModoB | Densidade como passo final no pipeline | ✓ |
| Após geração, antes de avaliação | Densidade como filtro pré-avaliação | |
| Em paralelo com ModoB | Densidade calculada em paralelo | |

**User's choice:** Final, após ModoB (após recomendação do agente)
**Notes:** Usuário solicitou recomendação. Agente recomendou passo final por ser natural com multiplicador final e zero refatoração. Usuário confirmou.

## Escopo de Aplicação

| Option | Description | Selected |
|--------|-------------|----------|
| Todas as estratégias | Densidade calculada para qualquer instrução gerada | ✓ |
| Apenas MutadorCognitivo | Densidade como bônus específico da estratégia cognitiva | |

**User's choice:** Todas as estratégias (após recomendação do agente)
**Notes:** Usuário solicitou recomendação. Agente recomendou todas as estratégias pois métrica universal funciona em qualquer output e bônus já diferencia MutadorCognitivo. Usuário confirmou.

---

## The Agent's Discretion

Nenhuma — todas as decisões foram explicitadas pelo usuário.

## Deferred Ideas

Nenhuma — a discussão se manteve no escopo da fase.
