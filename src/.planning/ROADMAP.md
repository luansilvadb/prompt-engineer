# Project Roadmap: Skill Optimizer

## Phase 1: Architectural Cleanup & Densification
**Goal:** Reduzir a complexidade ciclomática, remover código morto e densificar módulos para garantir responsabilidade única.
**Requirements:** ARC-01, ARC-02, ARC-03
**Success Criteria:**
1. Codebase livre de variáveis inativas, funções órfãs e imports desnecessários.
2. Branches condicionais complexos (especialmente em `mutations.py` e `drift_monitor.py`) extraídos para unidades menores.
3. O servidor FastAPI e o fluxo MCTS executam sem nenhum erro ou lentidão induzida pela refatoração.

## Phase 2: Judge "Caça-Defeitos" Mode
**Goal:** Atualizar o `AvaliadorDeSkill` para priorizar a detecção de contradições comportamentais (Modo B) no lugar de focar na estética do texto.
**Requirements:** JUD-01, JUD-02
**Success Criteria:**
1. O juiz passa a identificar paradoxos e contradições estruturais nas skills testadas, refletindo em notas realistas.
2. O sistema do `drift_monitor` absorve o novo comportamento do avaliador sem desativar a pipeline ou rejeitar todos os prompts válidos.
3. A verificação local comprova que o juiz agora falha a skill do "Espelho Distorcido" devidamente.
