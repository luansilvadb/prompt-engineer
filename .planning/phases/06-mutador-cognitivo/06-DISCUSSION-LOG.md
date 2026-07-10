# Phase 06: Mutador Cognitivo - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 06-mutador-cognitivo
**Areas discussed:** Mecanismo de injeção, Escopo da injeção, Registro da estratégia, Cobertura no MCTS

---

## Mecanismo de Injeção

| Option | Description | Selected |
|--------|-------------|----------|
| Prompt imperativo com template de seções | Prompt exige seções explícitas na skill sem mudar SelfReflectiveAgent | |
| Schema Pydantic embutido no prompt | Prompt inclui schema como referência textual | |
| Dois campos de output separados | Modificar SelfReflectiveAgent com campo extra | |
| Nova Signature DSPy específica | Herda SelfReflectiveAgent + adiciona raciocinio_estruturado | ✓ |

**User's choice:** Nova `MutadorCognitivoAgent` DSPy Signature — herda campos de `SelfReflectiveAgent` e adiciona `raciocinio_estruturado: str` como OutputField.
**Notes:** Usuário queria abordar os três conceitos (Pydantic, Python nativo, engenharia de prompts) de forma prática. A Signature separada foi escolhida para preservar `SelfReflectiveAgent` intacto e evitar regressões.

---

## Escopo da Injeção

| Option | Description | Selected |
|--------|-------------|----------|
| Raciocínio meta-cognitivo | Instrui COMO pensar; raciocinio_estruturado captura o processo | |
| Output estruturado tipado | Exige schema com seções obrigatórias; raciocinio_estruturado é JSON validado | |
| Ambos — processo + estrutura | raciocinio_estruturado captura derivação lógica E nova_instrucao segue template | ✓ |

**User's choice:** Ambos. `raciocinio_estruturado` é um dado estruturado com derivação lógica passo-a-passo e campos obrigatórios tipo "write-in" (`premissas`, `deducoes`, `conclusao`). A `nova_instrucao` deve ter seções obrigatórias derivadas desse raciocínio.
**Notes:** Usuário enfatizou que o agente deve ser forçado a preencher campos específicos — campos "write-in" obrigatórios garantem que a injeção seja válida, não genérica.

---

## Registro da Estratégia

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded como seed no StrategyRegistry | Registrada via código Python na inicialização | ✓ |
| Injetada no discovered_strategies.json | Tratada como estratégia dinâmica | |
| Módulo separado com fallback ao registry | Registry com prompt-template + roteamento no optimizer | (combinado com ✓) |

**User's choice:** Seed hardcoded no código Python (Opção 1 + elementos da Opção 3). O prompt-template fica no código; o `optimizer.py` roteia para `MutadorCognitivoAgent` quando a estratégia selecionada pelo bandit for `MutadorCognitivo`.
**Notes:** Justificativa do usuário: DSPy/Pydantic precisam de instanciação Python nativa; registro hardcoded garante robustez ao core. JSON externo seria frágil para agentes estruturais.

---

## Cobertura no MCTS

| Option | Description | Selected |
|--------|-------------|----------|
| Competidor normal no bandit UCB1 | Registrado como qualquer outra estratégia | |
| Peso inicial elevado (prior boosting) | Load com virtual counts positivos via load_priors() | ✓ |
| Garantia de uso mínimo | A cada N iterações, forçado como __DISCOVER__ | |

**User's choice:** Prior boosting via `load_priors()` com virtual counts positivos no início da otimização.
**Notes:** Garante exploração inicial sem alterar a lógica UCB1. Análogo ao comportamento do `__DISCOVER__` mas via mecanismo existente de priors.

---

## The Agent's Discretion

Nenhuma — todas as decisões foram explicitadas pelo usuário.

## Deferred Ideas

Nenhuma — a discussão se manteve no escopo da fase.
