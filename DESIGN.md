# Design System: Ultra-Minimalist Precision

Este documento define as diretrizes estéticas e técnicas da interface do projeto (Skill Optimizer MCTS), baseadas na estética **Ultra-Minimalista de Alta Precisão (Dev-Tool Premium)**. 

A inspiração arquitetural deriva de ferramentas modernas focadas em desenvolvedores, como Vercel, Linear e OpenAI, onde o foco absoluto está na densidade de informação e na ausência total de distrações visuais genéricas.

---

## 1. Princípios Fundamentais

1. **Foco Cirúrgico nos Dados:** A ferramenta lida com simulações matemáticas e árvores MCTS. O visual deve parecer um "painel de instrumentos de laboratório de software". Sem "blobs" coloridos, sem gradientes roxos genéricos.
2. **Monocromático Premium:** A interface opera quase puramente em preto, cinza-escuro e branco. Cores (azul, verde, vermelho) são estritamente reservadas para status semânticos.
3. **Densidade Tática:** Os tamanhos de fonte são ligeiramente menores que o padrão web (base `13px`) para permitir que painéis de logs e códigos sejam lidos sem excesso de rolagem.
4. **Física e Fricção:** Toda animação e transição possui um "peso" através do uso de curvas `cubic-bezier`, dando uma sensação tátil às interações.

---

## 2. Tipografia

A tipografia reflete limpeza e precisão geométrica.

*   **Fonte Principal (UI, Cabeçalhos e Corpo):** `Manrope`
    *   *Por quê?* É uma Sans-Serif moderna, técnica, altamente legível e com forte atitude profissional em pesos menores.
*   **Fonte de Código e Dados:** `JetBrains Mono`
    *   *Onde usar?* Logs de console, previews JSON, botões/tags numéricas, visualização das regras e scores dos nós.

---

## 3. Paleta de Cores (Tokens)

Toda a arquitetura CSS usa tokens rígidos. O fundo é escuridão total. As elevações ocorrem através da variação milimétrica do brilho cinza.

```css
:root {
    /* Fundo Absoluto */
    --bg-base: #000000; 
    
    /* Janelas e Painéis */
    --bg-surface: #0a0a0a;
    --bg-panel: #111111;
    
    /* Ações de Alto Contraste */
    --color-primary: #FFFFFF;
    --color-primary-hover: #EBEBEB;
    
    /* Status e Feedback Semântico */
    --color-secondary: #0070F3; /* Azul Vercel / Running */
    --color-success: #17C964;   /* Verde Sucesso */
    --color-warning: #F5A623;   /* Laranja Alerta */
    --color-danger: #F31260;    /* Vermelho Erro */
    
    /* Texto */
    --text-main: #EDEDED;
    --text-muted: #888888;
    
    /* Estrutura "Glass" Fina */
    --border-glass: rgba(255, 255, 255, 0.08);
    --border-active: rgba(255, 255, 255, 0.20);
}
```

---

## 4. Sombras e Efeitos Visuais (Milled Aluminum)

Abandonamos o conceito de "glassmorphism" borrado. A tridimensionalidade aqui é dada pelo **Efeito de Alumínio Usinado**.

*   **`--shadow-inset`:** `inset 0 1px 0 0 rgba(255, 255, 255, 0.06)`
    *   *Uso:* Adicionado aos painéis. Cria um filete de luz dura na borda superior interna do painel, imitando luz rebatendo em uma carcaça de metal.
*   **`--shadow-glow`:** `0 0 0 1px rgba(255, 255, 255, 0.15), 0 12px 32px rgba(0, 0, 0, 0.9)`
    *   *Uso:* Foco e destaque (ex: caminho ótimo do MCTS). Gera uma aura sutil sem parecer mágica brilhante barata.

---

## 5. Micro-Interações e Detalhes

### Curva de Transição Mestra
O sistema não usa `ease` genérico. Toda movimentação na tela é baseada na seguinte curva:
```css
--transition-snappy: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
```
Isso garante o comportamento "buttery smooth" consagrado por ecossistemas modernos (fricção alta no final da animação).

### Grids Estruturais
Zonas de visualização matemática complexa (como o canvas onde a **Árvore MCTS** é desenhada) recebem um padrão sutil de grade técnica em vez de liso sólido:
```css
background-image: 
    linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), 
    linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
```

### Componentes Semânticos: "Pills" CLI
Tags de número, scores e visitas em nós da árvore abandonam os grandes blocos coloridos para adotar o formato **Pill (Pílula)**: `border-radius: 12px`, padding mínimo, fonte minúscula monospace (10px) e fundo translúcido `rgba(255,255,255,0.05)`. 

### Scrollbars Customizadas
A experiência nativa de rolagem do SO deve ser sobrescrita em todo o site. Barras ultra-finas (6px) em tons de cinza/vidro translúcido, mantendo a tela imersiva.

---

## 6. Contratos de Qualidade (Backend MCTS)

O backend do Skill Optimizer MCTS enforca contratos estritos de qualidade (Design by Contract) para garantir a integridade do processo de otimização de instruções:

### 6.1 `IQualityGuard`
Enforca validações pré-commit essenciais:
*   **RN-01 (Linter):** Verifica violações do Ruff.
*   **RN-02 (Tests):** Executa suíte do Pytest e reporta falhas.
*   **RN-03 (Complexity):** Bloqueia funções com complexidade ciclomática $> 15$.
*   **RN-04 (Coverage):** Monitora cobertura de teste em módulos críticos (deve ser $\ge 70\%$).

### 6.2 `IDensityMultiplier`
Garante que o multiplicador de densidade lexical opere estritamente dentro das regras de negócio (RN-05):
*   Deve retornar $1.0$ se o threshold de densidade estiver desabilitado ou se as instruções (original vs. otimizada) tiverem o mesmo tamanho.
*   Invariante: o multiplicador resultante é limitado entre o piso e o teto definidos na configuração.

### 6.3 `IMCTSCancellation`
Força o cancelamento imediato de uma iteração MCTS caso o sinalizador de interrupção seja ativado. RN-06 define três checkpoints obrigatórios para fail-fast:
1.  Antes da seleção do nó.
2.  Imediatamente após a expansão do nó.
3.  Antes do início da simulação.

### 6.4 `IDriftGate`
O portão de controle de drift previne desvios de comportamento nos candidatos avaliados:
*   **RN-07 (Fail-Closed):** Qualquer exceção ou erro ao medir o drift causa a rejeição automática do candidato (segurança absoluta).
*   **RN-08 (Fail-Open):** Se o Golden Set de calibração estiver vazio ou ausente, a compilação segue com advertência explícita no log.

---

## 7. Taxonomia LLMBar — Golden Set & Drift Monitor

A arquitetura de avaliacao e calibracao do juiz segue a metodologia do paper **LLMBar** (Zeng et al., ICLR 2024), que estabelece um benchmark de meta-avaliacao para testar se um LLM evaluator consegue discernir outputs que seguem instrucoes (instruction following) de outputs que desviam mas possuem qualidades superficiais atraentes.

### 7.1 Status das Fases (LLMBar Implementation)

| Fase | Status | Descricao |
|---|---|---|
| Fase 2 — Prompting Strategies | **Concluida** | Rules (docstring) em producao. Metrics + Swap implementados mas NAO integrados (ver 7.5). |
| Fase 3 — Drift Metrics | **Concluida** | style_gap, style_drift_signal, category_accuracy integrados no DriftReport. |
| Fase 1 — Golden Set | **PARCIAL (7/21 probes, 5/6 categorias)** | Faltam NEIGHBOR e GPTOUT (categorias adversariais mais dificeis do LLMBar). As 4 categorias entregues (estilo, natural, constraint, manual, negation) sao as mais faceis. |
| Fase 4 — Pesos | **Ajuste manual provisorio (nao data-driven)** | densidade_informacional 1.0→1.4, acionabilidade 1.3→1.4 por julgamento qualitativo. MAE-driven adjustment real requer golden set ≥15 probes com cobertura por categoria. |
| Fase 5 — Testes | **Concluida** | 9/9 testes de cobertura passando. |

### 7.2 Categorias de Probes

| Categoria | Origem LLMBar | Status | Probes |
|---|---|---|---|
| `estilo` | Adversarial (Manual) | 3 probes | SD-1, SD-2, SD-3 |
| `natural` | Natural Set | 1 probe | NAT-1 |
| `constraint` | Constraint | 1 probe | CON-1 |
| `manual` | Adversarial (Manual) | 1 probe | MAN-1 |
| `negation` | Negation | 1 probe | NEG-1 |
| `neighbor` | Adversarial (Neighbor) | **PENDENTE** | — |
| `gptout` | Adversarial (GPTOut) | **PENDENTE** | — |

### 7.3 Metricas de Drift (Fase 3 — LLMBar)

- **`style_gap`**: `composite(SD-1) - composite(SD-3)`. Negativo = vies estetico confirmado (alarme critico). **Valor atual (2026-07-19, Rules-only em producao): +0.599** (SD-1: 0.939, SD-3: 0.340). Medicao unica deterministica sob temperature=0 — nao ha distribuicao amostral (stdev=0). Threshold de alarme: `style_gap < 0.2` (**provisorio** — recalibrar com ≥15 probes).
- **`style_drift_signal`**: Flag de auditoria que detecta buzzwords pomposas em >40% dos feedbacks textuais do juiz. **NUNCA penaliza automaticamente** — e sinal para investigacao humana. Threshold inicial (>40%) e provisorio.
- **`category_accuracy`**: Acuracia de `critical_rules` quebrada por categoria de probe.

**Nota sobre temperature=0**: `src/config.py` configura `temperature=0` por padrao, tornando o juiz deterministico. "Repeticoes do mesmo probe" produzem valores identicos (stdev=0, nao ha distribuicao amostral). **Agregados entre probes distintos** (offset, false rejections, category_accuracy) permanecem validos como metricas de cobertura de casos distintos. Nos experimentos abaixo, "1 medicao" = 1 chamada deterministica ao LLM.

### 7.4 Resultados do Isolamento de Componentes (2026-07-19)

Todas as medicoes sao deterministicas (temperature=0). Epsilon = 0.05 definido a priori para classificacao "≈" (neutro).

**Importante**: As configuracoes (a) e (b)/(c) usam Signatures diferentes:
- (a) usa `BaselineSignature` (docstring neutra e curta, criada para o experimento)
- (b) e (c) usam `AvaliadorModoBSignature` (framing "Modo B - Caca-Defeitos" + descricoes detalhadas das 6 dimensoes + 4 regras)
- O delta (b)−(a) **NAO isola as 4 regras** — ele mede a troca completa de Signature. A configuracao (d) abaixo isola o efeito das regras.

#### Configuracoes principais (7 probes, 1 medicao cada)

| Configuracao | style_gap | SD-1 | SD-3 | FalseRej | MissedV |
|---|---|---|---|---|---|
| (a) Baseline (`BaselineSignature` pura) | **0.074** | 0.949 | 0.874 | 10 | 5 |
| (b) Rules only (`AvaliadorModoBSignature` + regras, **producao**) | **0.599** | 0.939 | 0.340 | 10 | 5 |
| (c) Enhanced (Rules+Metrics+Swap) | **0.399** | 0.974 | 0.576 | 0 | 5 |

#### Experimento controlado (d): regras isoladas do framing (SD-1 e SD-3 apenas, 1 medicao cada)

| Configuracao | style_gap | SD-1 | SD-3 |
|---|---|---|---|
| (a) Baseline (`BaselineSignature` pura) | **0.074** | 0.949 | 0.874 |
| (d) `BaselineSignature` + 4 regras (sem framing) | **0.653** | 0.973 | 0.320 |
| (b) `AvaliadorModoBSignature` + regras (com framing) | **0.599** | 0.939 | 0.340 |

#### Decomposicao

| Componente | Delta | Interpretacao |
|---|---|---|
| (d)−(a) = +0.579 | Efeito isolado das 4 regras (sem framing) |
| (b)−(d) = −0.054 | Efeito residual do framing "Modo B" (essencialmente nulo) |
| (b)−(a) = +0.525 | Efeito total (regras + framing) |
| (b)−(c) = +0.200 | Custo de adicionar Metrics+Swap (piora o gap) |

**Conclusoes (todas baseadas em medicoes pontuais, n=1, deterministicas sob temperature=0):**
1. **Nesta medicao, as 4 regras respondem pela maior parte do ganho** (+0.579 dos +0.525 totais). O framing "Modo B - Caca-Defeitos" parece redundante (contribuicao residual de −0.054, dentro do epsilon). Sem distribuicao amostral, nao ha inferencia estatistica — o padrao e sugestivo, nao conclusivo.
2. **Mecanismo (hipotese, nao confirmado)**: SD-3 cai de 0.874→0.320 com as regras, enquanto SD-1 sobe levemente (0.949→0.973). As regras penalizam densidade informacional (15/100) e acionabilidade (25/100) do texto pomposo. Com base em inspecao qualitativa de N=1 caso, as perguntas auto-geradas pelo `MetricsGenerator` para SD-3 (ex: "O diagnostico inicia obrigatoriamente pela Fase I?") parecem ser satisfeitas pelo texto pomposo, que estruturalmente segue as fases — o Metrics avalia estrutura, nao clareza, e isso explicaria a recuperacao da nota do SD-3 sob Metrics. Esta e uma hipotese razoavel, nao um mecanismo verificado.
3. **Metrics PIOROU o style_gap em 0.200** (0.599 → 0.399, |delta| = 4× epsilon). Nao ha inferencia estatistica classica (temperature=0 → sem distribuicao amostral), mas a magnitude e grande o suficiente para a decisao de engenharia (nao integrar).
4. **EnhancedJudge NAO sera integrado em producao**: o custo (piora do style_gap, +2x chamadas API pelo Swap) supera o beneficio (zero false rejections).
5. **Missed violations = 5 em TODAS as configuracoes**: SD-2 esta sendo aprovado consistentemente — o hard-gate de `manteve_regras_criticas` nao esta funcionando como esperado. Investigar separadamente.

### 7.5 Estrategias de Prompting (Fase 2 — LLMBar)

1. **Rules** (EM PRODUCAO): 4 regras de priorizacao na docstring do `AvaliadorModoBSignature`.
2. **Self-Generated Metrics** (IMPLEMENTADO, NAO INTEGRADO): `MetricsGenerator` em `src/infrastructure/enhanced_judge.py`. NAO ativo em producao — dados de isolamento mostram que piora o style_gap.
3. **Swap and Synthesize** (IMPLEMENTADO, NAO INTEGRADO): `EnhancedJudge` em `src/infrastructure/enhanced_judge.py`. NAO ativo em producao — aleḿ da piora do style_gap, dobra o custo de API.

### 7.6 Limitacoes Conhecidas

- **Single-curator**: O golden set e curado por um unico anotador (Luan). Inter-rater reliability nao foi medida.
- **Tamanho**: 7 probes cobrem 5 categorias. O LLMBar original tem 419 instancias. A cobertura atual e suficiente para detectar regressoes grosseiras, mas insuficiente para calibrar thresholds com confianca estatistica.
- **Thresholds iniciais**: Os thresholds numericos (>0.05 no epsilon do isolamento, >40% no `style_drift_signal`, `style_gap < 0.2` no alarme) sao valores iniciais. Recalibrar quando golden set ≥15 probes.
- **Separacao gerador-juiz**: Probes gerados por LLM (NEIGHBOR, GPTOUT) devem usar um modelo DIFERENTE do juiz sendo avaliado para evitar contaminacao circular.
- **Hard-gate SD-2 nao funcional**: `manteve_regras_criticas` nao esta detectando violacao de regras em nenhuma configuracao testada. Requer investigacao dedicada.
- **Possivel simplificacao da signature de producao**: (b)−(d) = −0.054 sugere que a signature atual (`AvaliadorModoBSignature` com framing "Modo B - Caca-Defeitos") tem style_gap marginalmente pior que a versao enxuta testada em (d) (`BaselineSignature` + 4 regras). Investigar se vale simplificar a signature de producao — requer medicao de confirmacao com n>1 ou parafrases (nao apenas rerun deterministico).

### 7.7 Pesos das Dimensoes (Fase 4 — Ajuste Manual Provisorio)

`SCORE_WEIGHTS` em `src/signatures.py` (fonte unica de verdade):

| Dimensao | Peso | Justificativa |
|---|---|---|
| `nota_clareza` | 1.0 | Clareza e fundamental mas nao suficiente |
| `nota_formatacao` | 0.8 | Formatacao e importante mas secundaria |
| `nota_robustez` | 1.2 | Robustez anti-ambiguidade e critica |
| `nota_densidade_informacional` | 1.4 | Dimensao mais vulneravel ao vies estetico (ajuste manual provisorio) |
| `nota_acionabilidade` | 1.4 | Instruction following objetivo (ajuste manual provisorio) |
| `nota_anti_fragilidade` | 1.2 | Resistencia a edge cases |

**Procedimento de recalibracao (pendente — requer ≥15 probes)**: Coletar MAE por dimensao do `DriftReport`. Para dimensoes no quartil superior de MAE, inspecionar manualmente 3 probes com maior desvio. Se ≥2 forem erro de calibracao do golden set, corrigir o golden set, nao os pesos. Caso contrario, aplicar `weight_new = weight_old * (1 + MAE_normalized)` e renormalizar.
