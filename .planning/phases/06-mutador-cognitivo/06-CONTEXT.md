# Phase 06: Mutador Cognitivo - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Criar a estratégia `MutadorCognitivo` no `StrategyRegistry` com uma nova DSPy Signature (`MutadorCognitivoAgent`) que injeta derivação lógica estruturada (passo-a-passo com campos obrigatórios validados por Pydantic) nas skills geradas durante a exploração do MCTS, e registrá-la com prior boosting no bandit UCB1.

</domain>

<decisions>
## Implementation Decisions

### Nova DSPy Signature
- **D-01:** Criar `MutadorCognitivoAgent` como uma nova DSPy Signature independente, herdando os campos de entrada/saída de `SelfReflectiveAgent` e adicionando `raciocinio_estruturado: str` como OutputField. `SelfReflectiveAgent` permanece **intacto** — sem risco de regressão nos demais nós do MCTS.

### Escopo da Injeção
- **D-02:** `raciocinio_estruturado` captura derivação lógica passo-a-passo com campos obrigatórios (ex: `premissas`, `deducoes`, `conclusao`). O campo é validado por um Pydantic model/validator em `signatures.py` — não pode ser vazio nem genérico. `nova_instrucao` deve conter seções obrigatórias derivadas desse raciocínio (ex: `## Raciocínio`, `## Regras`, `## Conclusão`), conectando o processo de derivação ao output final.

### Registro no StrategyRegistry
- **D-03:** `MutadorCognitivo` é registrado como estratégia seed **hardcoded** no código Python (não via JSON externo) durante a inicialização do `StrategyRegistry`. O prompt-template da estratégia fica no código. O `optimizer.py` detecta quando a estratégia selecionada pelo bandit é `MutadorCognitivo` e roteia para `MutadorCognitivoAgent` em vez de `SelfReflectiveAgent`.

### Cobertura no MCTS
- **D-04:** `MutadorCognitivo` recebe **prior boosting** via `load_priors()` com virtual counts positivos ao inicializar o `MutationBandit`. Isso garante exploração inicial sem alterar a lógica de seleção UCB1. A frequência/peso do boosting é configurável via `config.py`.

### The Agent's Discretion
Nenhuma — todas as decisões foram explicitadas pelo usuário.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planejamento e Arquitetura
- `.planning/PROJECT.md` — Visão geral e constraints ("Tolerância a Regressões", "Isolamento de Estado").
- `.planning/ROADMAP.md` — Phase 06 success criteria (COGN-01).
- `.planning/REQUIREMENTS.md` — Definição de COGN-01.
- `.planning/codebase/ARCHITECTURE.md` — Arquitetura MCTS, pipeline de avaliação, fluxo de recompensa.
- `.planning/codebase/INTEGRATIONS.md` — Overview de integrações (DSPy, LiteLLM).
- `.planning/codebase/STACK.md` — Dependências principais.

### Contexto de Fases Anteriores
- `.planning/phases/05-avaliador-de-profundidade-heur-stica/05-CONTEXT.md` — Pipeline de avaliação em 3 camadas (textstat → sentence-transformers → AvaliadorModoB). O MutadorCognitivo opera APÓS esse pipeline.
- `.planning/phases/04-avaliador-de-profundidade-sem-ntica/04-CONTEXT.md` — Padrão singleton para modelos pesados (global na memória no startup).

### Arquivos de Código Críticos
- `src/signatures.py` — Onde `MutadorCognitivoAgent` (nova Signature) e seu validador Pydantic devem ser criados.
- `src/mutation_strategies/registry.py` — `StrategyRegistry` onde a seed hardcoded deve ser adicionada.
- `src/mutation_strategies/bandit.py` — `MutationBandit.load_priors()` para o prior boosting.
- `src/optimizer.py` — Roteamento de estratégia: detectar `MutadorCognitivo` e usar `MutadorCognitivoAgent`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/signatures.py`: Contém `SelfReflectiveAgent` (base para a nova Signature), `GeracaoSkill` (Pydantic validator de tamanho — padrão a seguir), `Avaliacao`/`AvaliacaoModoB` (padrão de Pydantic model com validators).
- `src/mutation_strategies/registry.py`: `StrategyRegistry.add_strategy(key, name, prompt)` — interface para registrar a seed. Chamar no `__init__` se a chave não existir (idempotente).
- `src/mutation_strategies/bandit.py`: `MutationBandit.load_priors(strategy_stats)` — recebe dict `{strategy: {count, mean_delta}}`. Usar para injetar virtual counts positivos de `MutadorCognitivo`.
- `src/optimizer.py`: Já faz import de `SelfReflectiveAgent` e chama `dspy.Predict(SelfReflectiveAgent)`. O roteamento por estratégia deve interceptar essa chamada.

### Established Patterns
- DSPy Signatures como classes que herdam os campos: `MutadorCognitivoAgent` segue o mesmo padrão de `SelfReflectiveAgent`.
- Pydantic validators com `@field_validator` em `signatures.py` — mesma abordagem para validar `raciocinio_estruturado`.
- Estratégias no registry como dicts `{name: str, prompt: str}` — o MutadorCognitivo adiciona seed na inicialização.

### Integration Points
- O `optimizer.py` usa a estratégia selecionada pelo bandit em `run_simulation()` ou equivalente. A detecção de `MutadorCognitivo` deve ser feita nesse ponto para rotear `dspy.Predict(MutadorCognitivoAgent)`.
- O campo `raciocinio_estruturado` retornado pelo agente pode ser logado no `MCTSNode` (ex: campo opcional) para auditoria/debug.

</code_context>

<specifics>
## Specific Ideas

- O schema de `raciocinio_estruturado` deve ter campos tipo "write-in" obrigatórios: o agente é forçado a preencher `premissas`, `deducoes`, `conclusao` (ou equivalente) — não pode ser string vazia.
- A nova instrução (`nova_instrucao`) deve ter seções marcadas em Markdown derivadas do raciocínio (ex: `## Premissas`, `## Regras Derivadas`), conectando o processo lógico ao output.
- O prior boosting de `MutadorCognitivo` no bandit deve ser configurável em `config.py` (ex: `cognitivo_prior_count`, `cognitivo_prior_mean_delta`).

</specifics>

<deferred>
## Deferred Ideas

Nenhuma — a discussão se manteve no escopo da fase.

</deferred>

---

*Phase: 06-mutador-cognitivo*
*Context gathered: 2026-07-10*
