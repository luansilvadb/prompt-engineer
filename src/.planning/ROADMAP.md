# Project Roadmap: Skill Optimizer

## Phase 1: Architectural Cleanup & Densification

**Goal:** Reduzir a complexidade ciclomática, remover código morto e densificar módulos para garantir responsabilidade única.
**Requirements:** ARC-01, ARC-02, ARC-03
**Plans:** 5/5 plans complete
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Create src/drift/ foundation: exceptions.py + models.py (ARC-03)
- [x] 01-02-PLAN.md — Create src/mutation_strategies/ package: registry, bandit (ARC-02), api (ARC-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-03-PLAN.md — Create src/drift/ services: golden, runner, metrics with ARC-02 helper extractions (ARC-02, ARC-03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-04-PLAN.md — Create src/drift/ gate/circuit_breaker/cache; delete dead helper (ARC-01, ARC-02, ARC-03)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-05-PLAN.md — Convert drift_monitor.py + mutations.py to shims, ARC-01 dead-code sweep, integration verification (ARC-01, ARC-03)

**Success Criteria:**

1. Codebase livre de variáveis inativas, funções órfãs e imports desnecessários.
2. Branches condicionais complexos (especialmente em `mutations.py` e `drift_monitor.py`) extraídos para unidades menores.
3. O servidor FastAPI e o fluxo MCTS executam sem nenhum erro ou lentidão induzida pela refatoração.

## Phase 2: Judge "Caça-Defeitos" Mode

**Goal:** Atualizar o `AvaliadorDeSkill` para priorizar a detecção de contradições comportamentais (Modo B) no lugar de focar na estética do texto.
**Requirements:** JUD-01, JUD-02
**Plans:** 1/? plans complete
Plans:
**Wave 1**
- [x] 02-01-PLAN.md — Injeção de classes e adaptadores do Modo B (JUD-01)
**Success Criteria:**

1. O juiz passa a identificar paradoxos e contradições estruturais nas skills testadas, refletindo em notas realistas.
2. O sistema do `drift_monitor` absorve o novo comportamento do avaliador sem desativar a pipeline ou rejeitar todos os prompts válidos.
3. A verificação local comprova que o juiz agora falha a skill do "Espelho Distorcido" devidamente.
