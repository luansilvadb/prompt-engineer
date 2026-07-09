# Phase 2: Judge "Caça-Defeitos" Mode - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 2-Judge "Caça-Defeitos" Mode
**Areas discussed:** Injeção do Modo B, Escopo das contradições detectadas, Calibração do DriftGate, Destino do modelo otimizado

---

## Injeção do Modo B

| Option | Description | Selected |
|--------|-------------|----------|
| Novo docstring no AvaliadorDeSkill | Substitui o docstring atual, muda comportamento globalmente | |
| Campo `modo_avaliacao` na Signature | InputField opcional, permite A/B, expande interface | |
| Classe separada `AvaliadorModoB(dspy.Signature)` | Isola completamente o novo comportamento, duas Signatures, seleção por parâmetro | ✓ |

**User's choice:** Classe separada `AvaliadorModoB`
**Notes:** O usuário priorizou isolamento completo do comportamento.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Parâmetro `modo='b'` em `_invoke_judge_with` | Seleciona o Predict dentro da função existente | |
| Flag no `DriftRunner.__init__` | Runner instanciado com modo, controle por configuração | |
| Método separado `run_modo_b()` no `DriftRunner` | Explícito, testável em isolamento, sem afetar caminho principal | ✓ |

**User's choice:** Método separado `run_modo_b()`
**Notes:** Preferência por explicitidade e testabilidade independente.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Por padrão toda avaliação usa Modo B | Modo A só como fallback/debug | ✓ |
| Modo B apenas no DriftGate, Modo A no otimizador | Separa intenções por etapa do pipeline | |
| Modo B controlado por configuração de job (via API) | Flexível, adiciona lógica de configuração | |

**User's choice:** Modo B como padrão global
**Notes:** Alinha com o goal da fase; Modo A fica como fallback sem exposição na API.

---

## Escopo das contradições detectadas

| Option | Description | Selected |
|--------|-------------|----------|
| Apenas violações de regras explícitas | Escopo controlado, resultado previsível | |
| Violações explícitas + paradoxos internos | Inclui instruções mutuamente exclusivas | |
| Tudo: violações + paradoxos + ambiguidades perigosas | Mais abrangente, mais difícil de calibrar | ✓ |

**User's choice:** Tudo — violações, paradoxos e ambiguidades perigosas
**Notes:** O usuário quer cobertura máxima de padrões que tornam agentes imprevisíveis.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Ordem fixa no docstring: detectar falhas primeiro | Instrui o LLM por prompt, sem garantia estrutural | |
| Novo OutputField `defeitos_encontrados` | Força enumeração de defeitos antes das notas, auditável | ✓ |
| Prompt imperativo sem mudar campos | Menos mudanças, menor garantia de obediência | |

**User's choice:** Novo OutputField `defeitos_encontrados`
**Notes:** A estrutura de saída DSPy garante a ordem de raciocínio do LLM.

---

| Option | Description | Selected |
|--------|-------------|----------|
| O campo entra no `Avaliacao` (Pydantic) | Acesso estruturado no DriftGate, mais invasivo | |
| O campo fica só na Signature (str bruto) | Menor cascata, menor rastreabilidade | |
| Novo modelo `AvaliacaoModoB(Avaliacao)` | Herda e adiciona o campo, isola a mudança | ✓ |

**User's choice:** `AvaliacaoModoB(Avaliacao)`
**Notes:** Isola a mudança sem quebrar o contrato existente de `Avaliacao`.

---

## Calibração do DriftGate

| Option | Description | Selected |
|--------|-------------|----------|
| Ajustar thresholds nos arquivos de configuração | Muda `spearman_floor` e `offset_alarm` | |
| Recalibrar os probes do Golden Set | Atualizar `ProbeExpectation` para refletir Modo B | ✓ |
| Ambos: novos probes + thresholds ajustados | Recalibração completa | |

**User's choice:** Recalibrar probes do Golden Set
**Notes:** Os thresholds ficam estáveis; as expectativas são que mudam.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Recalibrar probes existentes alterando valores esperados | Mesmos probes, notas atualizadas | |
| Criar novos probes específicos do Modo B | Segundo Golden Set dedicado, antigo preservado para Modo A | ✓ |
| Manter único Golden Set híbrido com expectativas por modo | Mais complexo | |

**User's choice:** Novos probes específicos do Modo B em arquivo separado
**Notes:** O Golden Set do Modo A é preservado para regressões; o novo inclui probes com defeitos explícitos.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Manter no mesmo arquivo `ausculta.py` | Dois Golden Sets por variável | |
| Arquivo separado `ausculta_modo_b.py` | Isolamento completo, alinha com padrão da Fase 1 | ✓ |
| Pasta `golden_sets/` com módulo por modo | Mais estruturado, overhead para 2 conjuntos | |

**User's choice:** `ausculta_modo_b.py` separado
**Notes:** Coerente com o padrão de módulos isolados estabelecido na Fase 1.

---

## Destino do modelo otimizado do avaliador

| Option | Description | Selected |
|--------|-------------|----------|
| Descartar o .json atual | Modo B começa fresh, .json do Modo A não serve | |
| Manter como fallback só para o Modo A | .json carregado apenas quando Modo A é invocado | |
| Renomear para `avaliador_modo_a_otimizado.json` + path separado para Modo B | Estrutura clara para os dois modelos | ✓ |

**User's choice:** Renomear + preparar path separado
**Notes:** `load_avaliador(modo='a'/'b')` seleciona o path correto. Modo B começa fresh.

---

| Option | Description | Selected |
|--------|-------------|----------|
| API não expõe o modo | Detalhe interno do pipeline | ✓ |
| API aceita `modo_avaliacao` como parâmetro opcional | Permite A/B externo, retrocompatível | |
| API expõe `strict_mode` booleano | Semântico, sem expor detalhe de implementação | |

**User's choice:** API não expõe o modo
**Notes:** Modo B é silenciosamente o default; contratos de API externos não mudam (JUD-02).

---

## the agent's Discretion

Nenhuma área foi delegada ao agente — todas as decisões foram tomadas pelo usuário.

## Deferred Ideas

- **Otimização Few-Shot do `AvaliadorModoB`**: Coletar exemplos de defeitos e treinar Few-Shot via DSPy. Requer o Golden Set do Modo B operacional primeiro.
- **Exposição do modo via API**: Para cenários futuros de A/B testing externo. Fora do escopo desta fase.
