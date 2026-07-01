# [Explore] Grounding da Recompensa × Drift do Juiz

**Data:** 2026-07-01
**Participantes:** usuário + ZCode (modo explore + perspectiva David Silver)
**Status:** Conclusão da fase de exploração — pronto para spike de medição antes de `/spdd-analysis`

---

## 1. Contexto e motivação

O projeto é um otimizador de skills (prompts) baseado em MCTS self-play, inspirado em
AlphaGo/AlphaZero. O Core (`src/optimizer.py`) muta uma skill, um juiz a pontua em 6
dimensões, um bandit aprende, e a memória Dyna-2 acumula experiências.

**Duas dores trazidas pelo usuário:**

1. **Juiz alucina/enviesa no longo prazo** quando recompilado por teleprompt.
2. **`discovered_strategies` sem filtro** — estratégias inventadas pelo agente são
   persistidas sem portão de qualidade.

**Hipótese central do projeto:** a maior alavanca de capacidade está na *organização
do raciocínio*, não apenas no modelo subjacente. Um sistema que descobre
"reflexos cognitivos" sozinho pode superar humanos em classes de problemas
relacionadas a planejamento, busca, verificação e descoberta de estratégias.

---

## 2. Diagnóstico raiz (a unificação)

As duas dores são **sintomas do mesmo problema**: **falta de âncora de recompensa
externa ao loop**. O sinal de recompensa é auto-referencial.

### Loop de feedback positivo confirmado no código

```
juiz pontua ─► experiências ─► [reward≥0.8] ─► teleprompter ─► salva cego ─► juiz
     ▲__________________________________________________________________│
                        nenhuma verdade externa entra aqui
```

Evidência direta:

- `src/teleprompter.py:22` — `melhores = [exp ... if exp.absolute_reward >= 0.8]`
  usa **notas que o próprio juiz deu**.
- `src/teleprompter.py:40-41` — `trivial_metric(...) return True` aceita **qualquer**
  demo que o LM produza, sem triagem.
- `src/signatures.py:88` `_invoke_judge` usa o módulo **global** carregado de
  `avaliador_otimizado.json`. Nenhuma leitura fora desse arquivo.
- `src/teleprompter.py:53` — `compilado.save(...)` é **incondicional**.

**Conclusão:** o juiz é um amplificador de preferência com realimentação positiva pura.
Drift é a consequência matemática esperada, não um bug.

### Espelho nas estratégias

```
__DISCOVER__ ─► estratégia nova ─[ NENHUM PORTÃO ]─► registry (só cresce)
                                                      │
                            bandit rebaixa as ruins (soft), mas nunca deleta
```

Qualquer portão de estratégia (dor 2) só é confiável se a recompensa que o alimenta
for confiável. **Logo, resolver a dor 1 é pré-requisito da dor 2.**

---

## 3. Perspectiva David Silver aplicada

Princípios relevantes trazidos à discussão:

- **A recompensa deve vir do ambiente, não da crença anterior do agente.** O AlphaGo
  funciona porque *ganhar/perder* é sagrado e externo.
- Silver rejeita RLHF porque humanos injetam viés — mas rejeitaria **com a mesma força**
  um juiz treinado nas próprias notas dele. É duplo risco de Goodhart.
- **Tabula rasa vs. âncora:** "regras do jogo imutáveis" (a fronteira) e "estratégias
  emergentes livres" (o que evolui dentro da fronteira) não são conflito — são a
  separação correta. A questão de design não é "filtro sim/não", mas *quais são as
  regras imutáveis do jogo*.

### Guardrail crítico que preserva o alinhamento com Silver

> **O portão VETA regressões. Ele nunca OTIMIZA o juiz em direção ao golden set.**

- ❌ "Escolher o few-shot que melhor bate as notas golden" → constrói rater RLHF,
  trava no teto humano, amplifica viés da baseline.
- ✅ "Rejeitar few-shot que piora o drift" → calibração de instrumento. Dentro do
  frame estável, o juiz continua livre para descobrir.

A diferença é `rejeitar se piorar` (veto barato) vs. `maximizar concordância`
(otimização cara e perigosa). **Implementar só a primeira.**

---

## 4. Hierarquia de grounding (espectro da âncora)

Onde o sistema está e para onde pode ir:

| Nível | O que ancoriza | Drift? | Super-humano? |
|---|---|---|---|
| **L0 — Auto-referência** *(hoje)* | Juiz opina sobre texto; é compilado das próprias notas | Composto, positivo | Não |
| **L1 — Âncora de calibração** *(A1)* | Conjunto congelado de notas verificadas externamente | Detectável, reversível | Não |
| **L2 — Âncora funcional** | Recompensa = performance medida de agente usando a skill | Baixo | Talvez |
| **L3 — Âncora mecânica** | Sinal verificável (testes passam, restrições satisfeitas) | ~Zero | Sim |
| **L4 — Ambiente real** *(AlphaGo)* | Tarefa com ground-truth total, self-play puro | Zero | Sim |

**Decisão:** caminho **pragmático** — implementar **L1 (A1)** agora. L2/L3 fica para a
fase "depois melhoramos". A1 estanca o sangramento e é pré-requisito operacional para
qualquer salto futuro.

---

## 5. Direção escolhida: A1 (Grounding por calibração)

Quatro componentes, mapeados no código existente:

| Componente | Função | Onde toca |
|---|---|---|
| **1. Golden set** | ~20–50 tuplas congeladas `(skill_orig, skill_otim, regras, 6 notas esperadas, flag críticas)` | Novo: `src/outputs/golden/golden_set.json` (read-only) |
| **2. Monitor de drift** | Roda o juiz contra o golden; calcula 4 métricas | Novo módulo; instancia `dspy.Predict(...)` à parte (não o global) |
| **3. Portão defensivo** | Só sobrescreve `avaliador_otimizado.json` se não piorar o drift | Envolve `compilado.save()` em `teleprompter.py:53` |
| **4. Circuit breaker** | Drift cruza limiar duro → rollback para snapshot | Manter `.bak` ou baseline no `golden/` |

### Loop A1 (resiste à degradação)

```
juiz pontua ─► experiências ─► [reward≥0.8] ─► teleprompter compila candidato
                                                       │
                                         ┌── candidato vs GOLDEN SET ──┐
                                         │   drift piorou?              │
                                         │   SIM → REJEITA, mantém velho │  ← veto
                                         │   NÃO → salva                 │
                                         └──────────────────────────────┘
GOLDEN SET (congelado, fora do loop) ──── a âncora nunca treina, só mede
```

### Quatro métricas de drift

| Métrica | Detecta | Papel |
|---|---|---|
| **Spearman** (correlação de ranking) | Juiz trocou a ordem relativa do que é bom/ruim | **Portão primário (Cenário 2 stealth)** |
| **Offset de escala** (média esperada − média predita) | "Tudo virou >0.9" (inflação) | **Alarme (Cenário 1, sintoma do usuário)** |
| **MAE por dimensão** | Em quais dos 6 eixos descalibrou | Diagnóstico |
| **Concordância das regras críticas** | Juiz parou de flaggear o que deveria | **Veto absoluto (hard-gate comprometido = catastrófico)** |

**Observação sobre o Cenário 2 (stealth):** o juiz pode manter notas estáveis (parece
calibrado) mas trocar silenciosamente o que considera bom. Offset NÃO detecta isso;
apenas Spearman detecta. Por isso Spearman é a métrica rei do portão, não offset.

---

## 6. Decisões tomadas (via AskUserQuestion)

### 6.1 Fonte do golden set → **(α) Anchor pairs**

Construção: ~20 pares óbvios de skill detonada (notas baixas) vs. skill limpa (notas
altas). Só o *ranking* precisa estar correto, não notas exatas.

**Justificativa:** para *detectar drift*, referência estável basta. Calibração
absoluta da baseline importa menos que sua imutabilidade. Pode-se congelar notas
aproximadas agora e refiná-las depois sem reescrever o mecanismo.

### 6.2 Estado do juiz atual → **"Não sei dizer"**

`avaliador_otimizado.json` pode ou não estar driftado; é incerto.

**Consequência de design:** é na verdade uma vantagem. A primeira coisa que o sistema
faz é responder empiricamente "o juiz está driftado?". A baseline de rollback passa a
ser o **juiz zerado** (`dspy.Predict(AvaliadorDeSkill)` cru, sem few-shot) — único
estado cuja ausência de drift é garantida por construção.

---

## 7. Modo de falha sutil identificado (premissa a verificar)

O BootstrapFewShot só adiciona demos positivos. Dois cenários de corrupção:

| Cenário | Mecanismo | Detecção |
|---|---|---|
| **1 — Inflação** *(sintoma do usuário)* | Few-shot = só skills aprovadas → juiz vira complacente → notas sobem uniformemente | Offset de escala dispara |
| **2 — Hipercriticismo stealth** | Few-shot = "skills que o juiz antigo achou ótimas" → juiz aprende o *estilo* de nota, não qualidade → notas estáveis mas ranking interno muda | Só Spearman detecta |

**Fumaça empírica já observada:** a última experiência no log tem `absolute_reward: 1.0`
(nota máxima) com feedback puramente elogioso (*"superioridade estrutural absoluta"*).
Um ponto só — não prova drift, mas é exatamente o sintoma do Cenário 1. O spike confirma
ou refuta.

---

## 8. Spike de medição (próximo passo — read-only)

Antes de formalizar via `/spdd-analysis`, rodar um **spike isolado e read-only** que
remove a cegueira sobre o estado real do juiz. Não toca no loop.

### Sujeitos

| Sujeito | O que é | Por quê |
|---|---|---|
| **S0** — juiz zerado | `dspy.Predict(AvaliadorDeSkill)` cru, sem `load()` | Baseline de drift-zero garantida por construção |
| **S1** — juiz atual | `dspy.Predict(...)` + `load(avaliador_otimizado.json)` | O juiz em produção hoje |

Mesmo LM em ambos (via `config.setup()`). Única diferença = few-shot compilado. Isola o
efeito do teleprompter.

### Probes (6 pares, ranking correto óbvio)

Construídos a partir da skill real `openspec-archive-change` (que tem
"CRITICAL ADVERSARIAL PROTOCOL" com 4 regras críticas explícitas — material ideal de probe).

| Probe | Construção | Ranking esperado | O que testa |
|---|---|---|---|
| **P1** | skill real intacta, preserva as 4 regras críticas | Alto, `manteve=True` | Baseline de concordância |
| **P2** | idêntica a P1, mas removo "NO HALLUCINATIONS" | `manteve=False` (hard gate) | O juiz ainda flaggeia? ← crítico |
| **P3** | skill colapsada: sem markdown, um parágrafo, regras removidas | Muito baixo | Detecção de degradação estrutural |
| **P4** | outra skill boa (parent da experiência real) | Alto, `manteve=True` | Diversidade de domínio |
| **P5** | skill MEDIANA mas com linguagem pomposa (jargão, superlativos) | Médio-baixo | Enganação por estilo (complacência estética) |
| **P6** | dois candidatos A (claramente melhor) e B (claramente pior) | A > B | Troca de ranking (Cenário 2 stealth) |

**Controle de ruído:** 3 repetições por probe × sujeito (LLM é estocástico). Variância
alta = sinal fraco, não drift.

### Medidas (S0 vs S1, mesmos probes)

1. **Spearman** — correlação de ranking entre S0 e S1. < 0.8 → drift de preferência.
2. **Offset de escala** — `(média S1) − (média S0)`. Positivo grande → Cenário 1.
3. **MAE por dimensão** — quais dos 6 eixos descalibraram. Diagnóstico.
4. **Concordância das regras críticas** — S1 ainda retorna `manteve=False` em P2/P3?
   Se não → hard-gate comprometido, veto absoluto.
5. **Variância entre runs** — desvio-padrão das 3 repetições.

### Matriz de interpretação (cada achado trava uma decisão de A1)

| Achado do spike | Significado | Decisão que trava |
|---|---|---|
| S0 ≈ S1 (Spearman > 0.8, offset < 5pts) | Juiz atual não está driftado | `avaliador_otimizado.json` é baseline de rollback válida |
| S1 inflou (offset > 10pts, Spearman ok) | Cenário 1 confirmado | Juiz zerado vira baseline; portão veta por offset |
| S1 trocou ranking (Spearman < 0.8) | Cenário 2 stealth | Portão veta por Spearman (offset não pegaria) |
| S1 não flaggeia P2/P3 | Hard-gate quebrado | Circuit breaker vira veto absoluto; alerta crítico |
| Variância alta | Ruído > sinal | Aumentar N; spike não conclusivo |

### Custo

- ~6 probes × 2 sujeitos × 3 repetições = **~36 chamadas de LM**.
- Curadoria dos probes: meia hora (derivados da skill real).
- Output: diagnóstico real do juiz + probes calibrados que viram o golden set (α).

### Escopo honesto (o que o spike NÃO faz)

- Não adiciona o golden set — usa probes ad hoc.
- Não toca no teleprompter — read-only puro.
- Não resolve as dores — apenas remove a cegueira.

---

## 9. Checkpoints do modo explore

| Condição | Estado | Nota |
|---|---|---|
| `problema_definido` | ✅ | Recompensa auto-referencial; teleprompter sem portão; save cego |
| `direcao_escolhida` | ✅ | A1: golden set (α) + monitor + portão defensivo + circuit breaker |
| `incertezas_mitigadas` | ✅ | Fonte da âncora (α) e estado do juiz (zerado como baseline) resolvidas |
| `codebase_mapeado` | ✅ | teleprompter.py, signatures.py, experience_store.py, config.py lidos |
| `premissas_implicitas` | ✅ (após spike) | Premissa do BootstrapFewShot será verificada empiricamente pelo spike |

**Sequência:** spike de medição → (resultado popula o golden set + decide baseline) →
`/spdd-analysis` com problema totalmente aterrado.

---

## 10. Ordinação das decisões (princípio da fundação)

```
A — recompensa confiável (drift sob controle)         ← A1, agora
     └─ pré-requisito de ─┐
                          ▼
B — portão de estratégias (régua reta)                ← depois
     └─ pré-requisito de ─┐
                          ▼
C — descobrir primitivas de raciocínio (evolução segura)  ← visão de longo prazo
```

Saltar direto para B ou C sem A é construir casa sem fundação — e é exatamente o que
está incomodando agora.

---

## 11. Mapeamento de código (referência rápida)

| Conceito | Arquivo:linha |
|---|---|
| Loop MCTS principal | `src/optimizer.py:370` (`optimize`) |
| Recompensa / juiz | `src/signatures.py:142` (`funcao_de_recompensa`) |
| Hard-gate de regras críticas | `src/signatures.py:113` (`_check_critical_rules`) |
| Score composicional (6 dimensões) | `src/signatures.py:116` (`_calculate_score`) |
| Invocação do juiz (módulo global) | `src/signatures.py:88` (`_invoke_judge`) |
| Carregamento do juiz compilado | `src/signatures.py:79` (`load_avaliador`) |
| Teleprompter (compilação) | `src/teleprompter.py:10` (`compilar_avaliador`) |
| Filtro de demos (reward ≥ 0.8) | `src/teleprompter.py:22` |
| `trivial_metric` (aceita tudo) | `src/teleprompter.py:40` |
| Save cego do juiz | `src/teleprompter.py:53` |
| `discovered_strategies` (registry sem portão) | `src/mutations.py:27` (`StrategyRegistry`) |
| Braço `__DISCOVER__` | `src/optimizer.py:231` (`_expand_node`) |
| Memória Dyna-2 | `src/experience_store.py:136` (`ExperienceStore`) |
| Configuração do LM | `src/config.py:30` (`setup`) |
| Hiperparâmetros MCTS | `src/config.py:62` (`get_mcts_config`) |

---

*Documento gerado em modo explore (read-only). Não contém código implementável —
apenas mapeamento, análise e desenho de experimento para validação.*
