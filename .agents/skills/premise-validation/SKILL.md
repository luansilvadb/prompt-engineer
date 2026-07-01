---
name: premise-validation
description: Use para aplicar o Protocolo de Validação de Premissas e garantir que o desenvolvimento ocorra apenas em cima de problemas comprovados de mercado.
---

# Protocolo de Validação de Premissas

**Objetivo:** Garantir que construímos apenas para problemas comprovados — nunca para hipóteses aguardando confirmação futura.

---

## Camada 1 — Definir Premissas e Criticidade

Antes de qualquer desenvolvimento, liste de **3 a 5 hipóteses centrais** do modelo de negócio. Classifique cada premissa de acordo com sua criticidade:

*   **Premissa Âncora (Crítica):** Hipóteses vitais sem as quais o produto ou funcionalidade perde totalmente o sentido de existir.
*   **Premissa Acessória (Secundária):** Hipóteses importantes de valor agregado ou de experiência do usuário, mas que não inviabilizam o produto sozinhas.

| # | Premissa | Tipo | Quem valida | Prazo |
|---|----------|------|-------------|-------|
| 1 | *ex: "nosso público-alvo sente dor X"* | *Âncora / Acessória* | *responsável* | *data* |
| 2 | | | | |
| 3 | | | | |
| ... | | | | |

> **Tag de rastreamento:** Use `[P-X]` ao final de cada achado coletado (ex.: `[P-1]`, `[P-2]`) para reconstruir o histórico em execuções fragmentadas. Se a execução for interrompida, o estado atual permanece identificável.

---

## Camada 2 — Coletar Evidências (Sem Vieses)

Para cada premissa, colete **no mínimo 2 fontes** de tipos diferentes.

### Regra de Mitigação de Viés de Confirmação
> [!WARNING]
> Feedbacks ou dados coletados de parentes, amigos próximos ou membros da própria equipe interna de desenvolvimento **NÃO** podem ser considerados como evidências válidas. É obrigatório obter fontes externas e usuários reais do mercado.

| Tipo | Exemplos de fonte |
|------|-------------------|
| **Quantitativa** | Pesquisas amplas, métricas de uso, taxas de conversão, dados consolidados de mercado, benchmarks. |
| **Qualitativa** | Entrevistas profundas com usuários reais, feedbacks reais de clientes, support tickets, comentários públicos em redes sociais. |

Documente cada evidência com a tag correspondente: `[P-X-evidência-01]`, `[P-X-evidência-02]`.

### Estrutura Rígida de Evidência:
Cada evidência coletada deve seguir este padrão de documentação:
- **Data da Coleta:** DD/MM/AAAA
- **Método/Origem:** (ex.: Entrevista gravada, Google Analytics, Post público no X)
- **Dado/Citação:** "Citar o trecho exato que comprova ou contradiz a hipótese" ou [Métrica/Gráfico/Link para Fonte]

---

## Camada 3 — Dashboard de Status

Classifique cada premissa com base nas evidências coletadas:

```
┌────────────────────────────────────────────────────────┐
│                    DASHBOARD DE VALIDAÇÃO              │
├──────────────┬──────────────┬──────────────────────────┤
│ PREMISSA     │   STATUS     │   BASE DA CLASSIFICAÇÃO  │
├──────────────┼──────────────┼──────────────────────────┤
│ P-1 (Âncora) │ Confirmada   │ _dado concreto cite aqui_│
│ P-2 (Âncora) │ Pendente     │ _amostra insuficiente_   │
│ P-3 (Aces.)  │ Descolada    │ _dado contradiz premissa_│
└──────────────┴──────────────┴──────────────────────────┘
```

### Critérios de classificação:
- **Confirmada:** Dado sólido (múltiplas fontes independentes convergindo) sustenta de forma clara a premissa.
- **Pendente:** Existem indícios, mas a amostra é insuficiente, inconsistente ou existem dados contraditórios leves.
- **Descolada:** Dado qualitativo ou quantitativo confiável **contradiz diretamente** a premissa.

---

## Camada 4 — Gate de Decisão

Após classificar todas as premissas, aplique as regras matemáticas e estruturais de aprovação:

| Condição | Ação |
|----------|------|
| **Confirmadas ≥ 60%** das premissas **E** nenhuma premissa Âncora descolada | Prosseguir com desenvolvimento |
| **Qualquer premissa Âncora Descolada** | **SUSPENDER desenvolvimento imediatamente**. Requer reformulação total do modelo de negócio ou pivotagem. |
| **Pendentes + Descoladas > 40%** | **SUSPENDER desenvolvimento**. Coletar mais evidências ou ajustar premissas acessórias. |

> **Definição operacional:** "> 40%" significa **mais de 2 em cada 5** premissas pendentes ou descoladas. Exemplo: com 5 premissas, se 2 forem pendentes OU descoladas, o gate abre em vermelho (desenvolvimento suspenso).

---

## Regra Inegociável

**Construímos para problemas confirmados — nunca para hipóteses esperando confirmação futura.** Se o gate indicar vermelho, retorne à Camada 1 com o modelo reformulado. Não avance para desenvolvimento até que a maioria das premissas e todas as premissas âncoras sejam confirmadas.

---

## Template de Preenchimento do Protocolo

Para aplicar este protocolo, preencha o modelo abaixo no arquivo de documentação do seu projeto:

```markdown
# Relatório de Validação de Premissas — [Nome do Projeto]

## 1. Definição de Hipóteses e Criticidade
- **[P-1] (Âncora):** [Descreva a hipótese] — Validação por: [Responsável] até [Data]
- **[P-2] (Âncora):** [Descreva a hipótese] — Validação por: [Responsável] até [Data]
- **[P-3] (Acessória):** [Descreva a hipótese] — Validação por: [Responsável] até [Data]

## 2. Evidências Coletadas
### [P-1]
- **[P-1-evidência-01] (Quantitativa/Qualitativa):**
  - Data: DD/MM/AAAA | Método: [Método]
  - Dado/Citação: "[Citação ou métrica]"
- **[P-1-evidência-02] (Quantitativa/Qualitativa):**
  - Data: DD/MM/AAAA | Método: [Método]
  - Dado/Citação: "[Citação ou métrica]"

## 3. Dashboard de Status
[Insira o Dashboard estruturado em tabela ou ASCII]

## 4. Gate de Decisão e Próximos Passos
- **Percentual de Validação:** X%
- **Status do Gate:** [VERDE / VERMELHO]
- **Decisão:** [Prosseguir / Suspender]
```

---

## Dica de Robustez

Em execuções fragmentadas ou com interrupções, as tags `[P-X]` e `[P-X-evidência-Y]` permitem remontar o estado de validação sem perda de contexto. Exemplo de fragmentação:

```
[Etapa 1 — Concluída]
  P-1 (Âncora): Confirmada [P-1-evidência-01] [P-1-evidência-02]
  P-2 (Âncora): Pendente [P-2-evidência-01]

[Etapa 2 — Pendente]
  P-2 (Âncora): coleta de evidência qualitativa adicional em andamento...
  P-3 (Acessória): não iniciada
```
