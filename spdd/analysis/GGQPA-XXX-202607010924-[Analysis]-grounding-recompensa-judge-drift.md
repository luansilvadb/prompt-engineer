# SPDD Analysis: Grounding da Recompensa e Detecção de Drift do Juiz

## Original Business Requirement

> duas coisas ta me incomodando primeiro, o juiz se for utilizado o teleprompt a longo prazo ele começa a (alucinar) fica enviazado, segundo, o discovered_strategies gerado pelo agente está sem filtro, mesmo que queremos evolução da IA precisamos da a ela o caminho certo a seguir Os processos mentais do ser humano surgiram por evolução.
>
> Estou propondo uma evolução do nosso Core, para que nosso projeto descubra novos "reflexos cognitivos" sozinho.
>
> Se isso funcionar, ele pode encontrar estratégias que nenhum humano concebeu.
>
> Isso poderia superar humanos? Em tarefas específicas, sim. [...]
>
> A IA das últimas décadas foi dominada por "escalar modelos": mais dados, mais parâmetros, mais computação. estou apostando que a maior alavanca está na **organização do raciocínio**, não apenas no modelo subjacente. [...] um sistema assim poderia tornar um mesmo modelo muito mais capaz em determinadas classes de problemas, porque ele estaria constantemente descobrindo maneiras melhores de usar suas capacidades. Isso não reproduziria toda a cognição humana, mas poderia reproduzir — e em alguns domínios superar — a parte relacionada a planejamento, busca, verificação e descoberta de estratégias.

**Requisito operacional derivado (consolidado da fase explore):**

1. **Dor 1 — Drift do juiz por teleprompt:** O juiz (`AvaliadorDeSkill`), quando recompilado a partir das próprias experiências aprovadas, acumula viés e degrada no longo prazo ("alucina/enviesa").
2. **Dor 2 — `discovered_strategies` sem filtro:** Estratégias inventadas pelo agente (`__DISCOVER__`) são persistidas incondicionalmente no registry, sem portão de qualidade.
3. **Visão:** Permitir evolução autônoma de "reflexos cognitivos" de forma *segura* — dar "o caminho certo a seguir" (fronteira imutável) sem engessar a descoberta (evolução dentro da fronteira).

**Escopo decidido na exploração:** caminho **pragmático (A1)** — ancorar a recompensa em um conjunto de calibração (golden set), com monitor de drift, portão defensivo e circuit breaker. A dor 2 fica explicitamente fora deste escopo (pré-requisito: a âncora precisa existir primeiro).

---

## Domain Concept Identification

### Existing Concepts (from codebase)

- **Juiz / Avaliador** (`AvaliadorDeSkill`, `src/signatures.py:58`): assinatura DSPy que pontua uma skill otimizada em 6 dimensões ortogonais (clareza, formatação, robustez, densidade informacional, acionabilidade, anti-fragilidade) + flag `manteve_regras_criticas`. Implementado como `dspy.Predict(AvaliadorDeSkill)` — instância global `avaliador_module`.
- **Função de recompensa** (`funcao_de_recompensa`, `src/signatures.py:142`): orquestra o juiz; aplica hard-gate (`_check_critical_rules` → reward 0.0) e score composicional ponderado (`_calculate_score`, pesos 0.8–1.3). Retorna `(score ∈ [0,1], feedback)`. É o sinal que alimenta todo o restante do sistema.
- **Teleprompter / Compilação do juiz** (`compilar_avaliador`, `src/teleprompter.py:10`): pega experiências com `absolute_reward >= 0.8`, constrói trainset `(skill_original → skill_otimizada)`, roda `BootstrapFewShot(metric=trivial_metric)` e **salva incondicionalmente** em `src/outputs/models/avaliador_otimizado.json`.
- **Experiência / Memória Dyna-2** (`ExperienceStore`, `src/experience_store.py:136`): persiste cada `(skill_hash, mutation_strategy, delta_reward, absolute_reward, feedback, instruction, parent_instruction)` em `experience_log.jsonl`. Bounded (500, FIFO) com temporal decay. É a fonte de dados do teleprompter.
- **`discovered_strategies` / Registry** (`StrategyRegistry`, `src/mutations.py:27`): armazena estratégias inventadas em `discovered_strategies.json`. Cresce monotonicamente; `add_strategy` persiste incondicionalmente (sem portão). **Fora de escopo aqui, mas conceitualmente acoplado** — qualquer porta futura depende da recompensa ser confiável.
- **Mutation Bandit** (`MutationBandit`, `src/mutations.py:77`): UCB1 que seleciona estratégias; seeded por priors da ExperienceStore. Soft-aprende a evitar estratégias ruins, nunca as deleta.
- **Loop MCTS** (`Optimizer`, `src/optimizer.py`): seleção (UCB) → expansão (bandit + SelfReflectiveAgent) → simulação (juiz via `funcao_de_recompensa`) → backprop. Consumidor final do sinal de recompensa.
- **Hard-gate de regras críticas** (`_check_critical_rules`, `src/signatures.py:113`): única âncora estável existente hoje — quando `manteve_regras_criticas=False`, reward é forçado a 0.0. É uma semente de grounding, mas cobre apenas um subconjunto.

### New Concepts Required

- **Golden Set (Conjunto de calibração)**: coleção **congelada e versionada** de tuplas `(skill_original, skill_otimizada, regras_adicionais, 6 notas esperadas por dimensão, flag manteve_regras_criticas esperada, verificador, versão)`. Âncora externa ao loop — **nunca entra no treino do teleprompter**, só é lida para medição. Lifecycle: imutável após curadoria; novas versões coexistem (versionamento), nunca sobrescrevem.
- **Monitor de drift**: mecanismo que instancia um juiz **à parte** (não o módulo global), roda-o contra o golden set e computa métricas de divergência (Spearman, offset de escala, MAE por dimensão, concordância das regras críticas). Conceitualmente um *instrumento de calibração*, não um otimizador.
- **Portão defensivo (vetor)**: ponto de controle que **vetoriza** — só permite sobrescrever `avaliador_otimizado.json` se o juiz candidato não piorar o drift em relação ao estado anterior. NÃO otimiza em direção ao golden set (isso viraria RLHF); apenas rejeita regressões.
- **Circuit breaker / Baseline de rollback**: estado de emergência para o qual o juiz reverte quando o drift cruza um limiar duro. Decidido como **juiz zerado** (`dspy.Predict(AvaliadorDeSkill)` sem few-shot) — único estado cuja ausência de drift é garantida por construção.

#### Key Business Rules

- **BR1 (Princípio do veto, não otimização):** O portão **veta regressões**; **nunca** otimiza o juiz em direção às notas do golden set. Cruzar essa linha transforma calibração de instrumento em rater RLHF — amplifica o viés da baseline e trava o sistema no teto humano.
- **BR2 (Isolamento da âncora):** O golden set **nunca** entra no trainset do teleprompter. A âncora que mede não pode treinar o que ela mede.
- **BR3 (Imutabilidade da âncora):** Notas do golden set são congeladas após curadoria. A estabilidade da referência importa mais que sua calibração absoluta.
- **BR4 (Hard-gate é veto absoluto):** Se a concordância das regras críticas cair (juiz para de flaggear violações), o circuit breaker dispara como veto absoluto — o hard-gate de `funcao_de_recompensa` não pode virar letra morta.
- **BR5 (Métrica rei = Spearman):** A correlação de ranking é o sinal primário do portão, porque detecta drift *stealth* (Cenário 2 — notas estáveis, ranking interno trocado) que o offset de escala não detecta.
- **BR6 (Escopo explícito):** Este requisito resolve **somente** o grounding da recompensa. `discovered_strategies` fica para fase posterior, e é pré-requisito deste: sem recompensa confiável, qualquer porta de estratégia usa régua torta.

---

## Strategic Approach

### Solution Direction

Ancorar o sinal de recompensa com um **conjunto de calibração (golden set)** externo ao loop, e transformar a recompilação do juiz de uma operação cega (`save` incondicional) em uma operação **sob prova** (compila candidato → mede drift vs. golden → só persiste se não regredir). A recompensa deixa de ser puramente auto-referencial e passa a ter uma referência imutável contra a qual o drift é detectável, mensurável e reversível.

Direção geral do fluxo de dados:
```
HOJE:  experiencias ─► [reward≥0.8] ─► teleprompter.compile() ─► save CEGO ─► juiz pior
A1:    experiencias ─► [reward≥0.8] ─► teleprompter.compile() ─► candidato
                                                          │
                                          candidato vs GOLDEN SET ─► monitor de drift
                                                          │
                                          drift piorou? ─► SIM: REJEITA + mantém atual (veto)
                                                          └─► NÃO: save + snapshot.bak
GOLDEN SET (congelado, fora do loop) ──── nunca treina, só mede
```

A decisão arquitetural central é **não introduzir nenhum novo consumidor de recompensa** — apenas interpor um instrumento de medição no ponto único onde o juiz é persistido (`compilar_avaliador` / `compilado.save()`). Isso mantém o acoplamento mínimo e o blast radius pequeno.

Aproveita os padrões existentes do projeto:
- **Persistência JSON/JSONL** (sem DB) — golden set segue o mesmo formato do ExperienceStore e do avaliador compilado.
- **Estrutura `src/outputs/<recurso>/`** — golden set vive em `src/outputs/golden/`.
- **Padrão de módulos com instância de classe + `_store_path()` + `_load()/save()`** — monitor/golden seguem o mesmo idioma do `StrategyRegistry` e `ExperienceStore`.
- **Carregamento explícito via `dspy.Predict(Signature)`** — o monitor instancia seu próprio juiz isolado, não toca no módulo global.

### Key Design Decisions

- **KDD1 — Fonte do golden set = anchor pairs (α):** Construção a partir de ~20 pares de ranking correto óbvio (skill detonada vs. skill limpa), exigindo apenas *ordem* correta, não notas exatas.
  - *Trade-offs:* Custo de criação baixíssimo; credibilidade da âncora baixa-média, **mas suficiente para detectar drift** (referência estável é o que importa para medição, não verdade absoluta).
  - *Recomendação:* Adotar α agora. Upgrades futuros (consenso multi-modelo β, ou curadoria humana γ) trocam o *conteúdo* do arquivo sem reescrever o mecanismo.
  - *Rationale:* Para *detectar* drift, ranking estável basta. A âncora pode ser congelada imperfeita hoje e refinada depois sem invalidar o portão.

- **KDD2 — Baseline de rollback = juiz zerado:** Em vez do `avaliador_otimizado.json` atual (estado de drift incerto), o snapshot de emergência é `dspy.Predict(AvaliadorDeSkill)` sem few-shot.
  - *Trade-offs:* Perde qualquer ganho legítimo do teleprompter em caso de trigger; mas é o único estado cuja ausência de drift é garantida por construção.
  - *Recomendação:* Adotar. Resolve a incerteza ("o juiz atual está driftado?") sem apostar — o monitor responde empiricamente, e a baseline segura é o estado sem viés few-shot.

- **KDD3 — Vetor, não otimizador:** O portão rejeita regressões; não busca o few-shot que maximiza concordância com o golden.
  - *Trade-offs:* Pode aceitar candidatos mediocres (qualquer um que não piore). Mas o veto barato é mais seguro que a otimização cara.
  - *Recomendação:* Implementar **somente** o veto. Otimização em direção ao golden é o anti-pattern que este requisito existe para evitar.

- **KDD4 — Métrica primária = Spearman; offset e MAE = diagnóstico; concordância de regras = veto absoluto:** Cada métrica assume um papel distinto, porque cada uma detecta um modo de falha diferente.
  - *Trade-offs:* Múltiplas métricas = maior complexidade no monitor. Mas é necessário — nenhuma métrica isolada cobre todos os modos de drift.
  - *Recomendação:* Hierarquizar: `concordância de regras` (veto binário) > `Spearman` (portão primário de ranking) > `offset` (alarme de inflação) > `MAE` (diagnóstico dimensional).

- **KDD5 — Ponto de integração = `compilar_avaliador` (não o endpoint HTTP):** O portão vive dentro da função de compilação, não no router.
  - *Trade-offs:* Torna o portão aplicável a qualquer chamador (router, CLI, futuro scheduler). Acopla a lógica de drift ao módulo de teleprompt.
  - *Recomendação:* Centralizar no `compilar_avaliador`. O endpoint `POST /api/train-judge` (`jobs.py:167`) já retorna `success/falha` — só precisa propagar um novo motivo de falha ("drift rejeitado").

### Alternatives Considered

- **Few-shot contrastivo (pares bom vs. ruim no mesmo pai):** Ensina a *fronteira*, não só a região positiva. *Rejeitado para este escopo* — resolve o viés de complacência mas não cria âncora externa; é complementar a A1, não substituto. Anotado como evolução pós-A1.
- **Reset/decay periódico do pool de demos:** Barato, alinhado com "Era of Experience". *Rejeitado como solução primária* — retarda o drift mas não cria referência estável para detectá-lo. Útil como higiene secundária.
- **Pular para L2/L3 (âncora funcional/mecânica — recompensa = performance verificada de agente usando a skill):** É onde super-humano vira possível (Silver). *Rejeitado para agora* por custo (requer harness de execução + suíte de tarefas + sinal de outcome). A1 é pré-requisito operacional: sem calibração estável, não se mede se L2/L3 funciona. Caminho = "depois melhoramos".
- **Golden set via curadoria humana total (γ) ou consenso multi-modelo (β):** Âncoras mais fortes. *Rejeitadas para now* por custo/benefício — α é suficiente para detecção de drift e upgrade é somente de conteúdo.

---

## Risk & Gap Analysis

### Requirement Ambiguities

- **A1 — O que conta como "piorar o drift"?** O portão precisa de um limiar de rejeição por métrica. O requisito não especifica valores (ex.: Spearman < 0.8? offset > X pontos? quantas dimensões no MAE?). *Necessita definição no REASONS Canvas* — propostas em §8 do documento de explore servem de起点, mas precisam ser calibradas pelo spike.
- **A2 — Variância do LLM vs. drift real:** O juiz é estocástico. Uma queda de Spearman pode ser ruído, não drift. *Quantas repetições por probe definem "drift" vs. "ruído"?* Sem isso, o portão pode vetar falsamente (ou aprovar falsamente).
- **A3 — Políticas de evolução do golden set:** Embora imutável por versão, *como* novas versões são criadas e promovidas? Versão automática por data, ou curadoria humana? Impacta a credibilidade da âncora a longo prazo.
- **A4 — Comportamento quando o golden set está vazio/ausente:** O portão deve falhar-aberto (permitir save) ou falhar-fechado (bloquear)? Falha-aberto preserva o comportamento atual; falha-fechado protege mas pode travar o sistema em deploy limpo.

### Edge Cases

- **EC1 — Candidato piora em uma dimensão mas melhora em outra:** Soma? Veto se qualquer uma piorar? Veto só nas críticas (robustez, acionabilidade)? A regra de composição do `_calculate_score` (pesos 0.8–1.3) sugere que dimensões têm importância diferencial — o portão precisa respeitar essa hierarquia.
- **EC2 — Golden set não cobre o domínio do candidato:** Se o juiz foi compilado para um tipo de skill não representado nos probes, o drift medido pode não refletir o drift real. *Coverage do golden set* é uma restrição de validade.
- **EC3 — BootstrapFewShot produz demos vazios/instáveis:** `trivial_metric` sempre retorna `True`; se o compile produz zero demos bootstrapped, o "candidato" é equivalente ao juiz zerado — o portão compararia dois estados quase idênticos.
- **EC4 — Concorrência de compilação:** `_compile_lock` (`teleprompter.py:8`) já protege contra compilações simultâneas, mas o monitor de drift roda *durante* a janela travada — pode estender criticamente a seção crítica.
- **EC5 — Juiz zerado falha em produzir notas parseáveis:** O `validar_nota` (`signatures.py:42`) já trata strings não-numéricas, mas o juiz sem few-shot pode ser mais propenso a formatos inconsistentes — afeta a medição do S0 (baseline).
- **EC6 — Snapshot de rollback corrompido/inexistente em deploy limpo:** Sem `avaliador_otimizado.json` e sem snapshot, o circuit breaker não tem para onde voltar — precisa do juiz zerado como fallback sempre-disponível.

### Technical Risks

- **R1 — Custo de LLM do monitor:** Cada recompilação agora exige rodar o juiz (candidato) + preferivelmente o juiz anterior contra o golden set inteiro. Com N probes × K repetições × 2 juízes, o custo por `train-judge` sobe. *Mitigação:* cache das medições do juiz anterior; golden set pequeno (≤30).
- **R2 — Acoplamento sutil ao módulo global:** O monitor **não pode** usar `avaliador_module` global (contaminaria o estado). Precisa instanciar `dspy.Predict(AvaliadorDeSkill)` separadamente e carregar o `.json` do candidato nele. *Risco de DSPy:* instâncias de `Predict` compartilham state via `dspy.settings` — verificar se o few-shot é realmente isolado por instância.
- **R3 — Falsa sensação de segurança:** O portão detecta drift *contra o golden set*. Se o golden set é pequeno ou enviesado (α é imperfeito), o portão aprova drift não-coberto. *Mitigação:* documentar explicitamente a cobertura; tratar A1 como "necessário, não suficiente".
- **R4 — Goodhart reverso:** Se o time começa a "tunar o portão para passar" (ajustar limiares até candidatos problemáticos serem aprovados), a âncora perde valor. *Mitigação:* limiares são *constantes*, não parâmetros operacionais; mudanças exigem bump de versão do golden.
- **R5 — Interpretação do "drift stealth" (Cenário 2):** O sintoma que o usuário reportou (inflação) é o Cenário 1, detectável por offset. Mas o Cenário 2 (ranking trocado, notas estáveis) é mais traiçoeiro e só Spearman pega. *Risco:* focar só no sintoma relatado e perder o stealth. *Mitigação:* Spearman como métrica rei (KDD4).
- **R6 — Persistência atômica:** O ExperienceStore já faz save atômico (temp+rename). O snapshot de rollback e o golden set precisam do mesmo padrão — corrupção parcial num rollback de emergência é catastrófica.

### Acceptance Criteria Coverage

O requisito original não traz ACs formais. Os ACs implícitos são derivados das duas dores + da visão de evolução segura:

| AC# | Description | Addressable? | Gaps/Notes |
|-----|-------------|--------------|------------|
| AC1 | O juiz não degrada (drift detectável) no longo prazo após recompilações repetidas por teleprompt | **Yes** | A1 torna o drift detectável e reversível. Limiares exatos dependem do spike (A1, A2). |
| AC2 | É possível saber, empiricamente, se o juiz atual está driftado | **Yes** | Monitor de drift + spike inicial respondem isto diretamente. |
| AC3 | Uma recompilação que piore o juiz é rejeitada (não persiste) | **Yes** | Portão defensivo (vetor) no `compilar_avaliador`. |
| AC4 | Existe um caminho de recuperação (rollback) quando o drift é catastrófico | **Yes** | Circuit breaker → juiz zerado (KDD2). |
| AC5 | `discovered_strategies` tem portão de qualidade | **No (out of scope)** | Explicitamente fora do escopo A1. É a fase B, pré-requisito deste. Documentado na ordenação A→B→C. |
| AC6 | A evolução autônoma ("reflexos cognitivos") permanece possível sem engessar | **Partial** | A1 não toca no `__DISCOVER__` nem no bandit. Garante apenas que a *recompensa* que os alimenta é confiável. A evolução em si não é restringida — apenas ancorada. |
| AC7 | As regras críticas (hard-gate) continuam sendo enforced após recompilações | **Yes** | BR4: concordância das regras críticas é veto absoluto do circuit breaker. |

**Cobertura:** 5/7 totalmente endereçáveis, 1 parcial (evolução não-engessada — intencionalmente não restrita), 1 explicitamente fora de escopo (AC5, fase B).

---

*Análise gerada pela fase `/spdd-analysis` do workflow SPDD. Documento de explore de origem: `spdd/explore/20260701_091913-[Explore]-grounding-recompensa-judge-drift.md`. Não contém detalhes de implementação — esses pertencem ao `/spdd-reasons-canvas`.*
