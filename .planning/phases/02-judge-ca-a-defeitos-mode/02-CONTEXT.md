# Phase 2: Judge "Caça-Defeitos" Mode - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Atualizar o `AvaliadorDeSkill` para operar em Modo B ("Caça-Defeitos"), priorizando a detecção de contradições comportamentais, paradoxos internos e ambiguidades perigosas antes de qualquer avaliação estética. Garantir que o pipeline do `DriftGate` absorva corretamente as reprovações geradas pelo Modo B, incluindo a criação de um Golden Set dedicado e a reestruturação dos arquivos de modelo otimizado.

**Fora do escopo desta fase:**
- Alteração da lógica MCTS (UCT, exploração/exploração)
- Mudanças nos contratos de endpoints da API FastAPI
- Otimização Few-Shot do `AvaliadorModoB` (pode acontecer em fase posterior)

</domain>

<decisions>
## Implementation Decisions

### Injeção do Modo B na Signature

- **D-01:** Criar uma **classe separada `AvaliadorModoB(dspy.Signature)`** em `signatures.py`, isolando completamente o novo comportamento sem alterar o `AvaliadorDeSkill` (Modo A). As duas classes coexistem; o Modo A fica disponível apenas como fallback/debug.
- **D-02:** O `AvaliadorModoB` inclui um **novo `OutputField` `defeitos_encontrados`** (lista de strings enumerando violações, paradoxos e ambiguidades detectadas), posicionado antes de `feedback_detalhado` e das notas para forçar estruturalmente o raciocínio do LLM na ordem correta.
- **D-03:** **Por padrão, toda avaliação usa o Modo B.** O Modo A fica disponível apenas como fallback/debug — não é exposto na API de jobs.
- **D-04:** O `DriftRunner` expõe um **método separado `run_modo_b()`** para invocar o `AvaliadorModoB`. Explícito, testável em isolamento, sem afetar o caminho principal do Modo A.

### Escopo das Contradições Detectadas

- **D-05:** O `AvaliadorModoB` deve detectar **tudo**: violações de regras explícitas (passadas em `regras_adicionais` e no corpo da skill) + paradoxos internos (instruções mutuamente exclusivas) + ambiguidades perigosas (padrões que tornam o comportamento do agente imprevisível). O campo `defeitos_encontrados` enumera cada item encontrado.
- **D-06:** Criar um **novo modelo Pydantic `AvaliacaoModoB(Avaliacao)`** que herda `Avaliacao` e adiciona `defeitos_encontrados: list[str]`. Isso isola a mudança sem quebrar o contrato atual de `Avaliacao` usado pelo Modo A e pelo `DriftGate` existente.

### Calibração do DriftGate

- **D-07:** Criar um **arquivo separado `ausculta_modo_b.py`** com um novo Golden Set dedicado ao Modo B. O arquivo `ausculta.py` original (Modo A) é preservado para regressões de debug. O novo Golden Set inclui probes com violações explícitas, paradoxos e ambiguidades — cenários que o Modo A não testava. As expectativas de nota nos probes do Modo B refletem o regime de notas mais baixas (ex: ~0.665 para skills disfuncionais).
- **D-08:** Os thresholds de `DriftThresholds` (spearman_floor, offset_alarm) **não são alterados** — a recalibração acontece nas expectativas dos probes, não nos limites do gate.

### Destino do Modelo Otimizado

- **D-09:** Renomear o arquivo atual `outputs/models/avaliador_otimizado.json` para **`avaliador_modo_a_otimizado.json`**. Preparar o path `avaliador_modo_b_otimizado.json` para uso futuro. A função `load_avaliador()` em `signatures.py` recebe um parâmetro `modo` ('a' ou 'b') e seleciona o path correto.
- **D-10:** O `AvaliadorModoB` **começa fresh** (sem Few-Shot carregado). O arquivo `.json` do Modo A não tem utilidade para o Modo B — exemplos de caça-defeitos precisariam ser coletados separadamente (fora do escopo desta fase).
- **D-11:** **A API de jobs (`routers/jobs.py`) não expõe o conceito de modo de avaliação.** O modo é um detalhe interno do pipeline. O default Modo B é aplicado silenciosamente sem parâmetros externos.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planejamento e Requisitos
- `.planning/ROADMAP.md` — Goal e success criteria da Phase 2 (JUD-01, JUD-02)
- `.planning/REQUIREMENTS.md` — Requisitos JUD-01 e JUD-02 detalhados
- `.planning/PROJECT.md` — Decisões de arquitetura e constraints do projeto

### Código do Avaliador
- `signatures.py` — `AvaliadorDeSkill`, `Avaliacao`, `_invoke_judge_with`, `SCORE_WEIGHTS`, `calcular_composite` — ponto de partida para criar `AvaliadorModoB` e `AvaliacaoModoB`
- `drift/runner.py` — `DriftRunner` e o método `run()` — adicionar `run_modo_b()` aqui
- `drift/gate.py` — `DriftGate.avaliar_candidato()` — verificar compatibilidade com `AvaliacaoModoB`
- `drift/metrics.py` — `medir_drift()` e `_compute_concordance_and_violations()` — verificar se aceita probes do Modo B
- `drift/models.py` — `DriftReport`, `GateDecision`, `DriftThresholds`, `GoldenProbe`, `ProbeExpectation` — entender o schema antes de criar `ausculta_modo_b.py`

### Golden Set Existente
- `ausculta.py` — Golden Set do Modo A; preservar para regressões. Usar como referência de estrutura para `ausculta_modo_b.py`

### Mapeamento do Codebase
- `.planning/codebase/ARCHITECTURE.md` — Fluxo de dados do pipeline
- `.planning/codebase/CONCERNS.md` — Acoplamentos conhecidos

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AvaliadorDeSkill` (signatures.py L58-75): Estrutura de Signature DSPy a ser espelhada em `AvaliadorModoB`. Mesmos InputFields, adicionar `defeitos_encontrados` OutputField antes dos demais.
- `Avaliacao` (signatures.py L32-56): Modelo Pydantic base; `AvaliacaoModoB` herda dele adicionando `defeitos_encontrados: list[str]`.
- `_invoke_judge_with` (signatures.py L93-121): Função parametrizada que já suporta módulos intercambiáveis — base para `run_modo_b()` no `DriftRunner`.
- `calcular_composite` e `SCORE_WEIGHTS` (signatures.py L126-154): Não mudam — o cálculo de score composto é o mesmo nos dois modos.
- `load_avaliador()` (signatures.py L79-86): Adaptar para aceitar `modo='a'/'b'` e selecionar o path do arquivo `.json` correspondente.

### Established Patterns
- **Módulos isolados** (padrão da Fase 1): cada arquivo tem responsabilidade única. `ausculta_modo_b.py` deve ser autossuficiente como `ausculta.py`.
- **Funções auxiliares simples** (não OO complexo): `run_modo_b()` é um método direto, não uma hierarquia de classes.
- **Veto absoluto no gate** (`gate.py` L34-40): `critical_rules_violated` ainda é o passo 1 do `DriftGate`. `AvaliacaoModoB.manteve_regras_criticas` (herdado de `Avaliacao`) alimenta esse passo.

### Integration Points
- `DriftRunner.run()` → `run_modo_b()`: novo método que usa `AvaliadorModoB` em vez de `AvaliadorDeSkill`.
- `DriftGate.avaliar_candidato()`: recebe `DriftReport` (não `Avaliacao`), então a mudança em `AvaliacaoModoB` não afeta diretamente o gate — o runner computa o relatório internamente.
- `funcao_de_recompensa()` (signatures.py L164-178): continua usando `_invoke_judge` (Modo A) para guiar o MCTS — **não alterar** nesta fase.
- `drift_monitor.py`: verificar se ainda usa `avaliador_otimizado.json` diretamente ou apenas via `load_avaliador()`.

</code_context>

<specifics>
## Specific Ideas

- **Skill "Espelho Distorcido"**: O success criterion do ROADMAP menciona que a verificação local deve comprovar que o Modo B reprova esta skill. O Golden Set do Modo B deve incluir um probe baseado nela (skill com instrução autocontraditória, nota esperada baixa).
- **Exemplo de calibração de nota**: PROJECT.md documenta que o Modo B corrigiu a nota de 0.96 → 0.665 para a skill do "Espelho Distorcido". Os probes de `ausculta_modo_b.py` devem ter `expected_composite ≈ 0.665` para skills disfuncionais e `expected_composite ≈ 0.85+` para skills bem construídas.
- **`defeitos_encontrados` como lista**: Cada item deve ser uma string curta e descritiva, ex: `["Regra 'seja conciso' contradiz 'explique cada passo'", "Campo X nunca definido mas referenciado em Y"]`.

</specifics>

<deferred>
## Deferred Ideas

- **Otimização Few-Shot do `AvaliadorModoB`**: Coletar exemplos rotulados de defeitos e treinar Few-Shot via DSPy BootstrapFewShot. Requer Golden Set do Modo B funcionando primeiro — próxima fase natural.
- **Exposição do modo via API**: Se no futuro houver necessidade de A/B testing externo, adicionar parâmetro `modo_avaliacao` ao endpoint de jobs. Por ora, decisão é manter como detalhe interno.

</deferred>

---

*Phase: 2-Judge "Caça-Defeitos" Mode*
*Context gathered: 2026-07-09*
