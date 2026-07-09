# Requirements: Skill Optimizer

**Defined:** 2026-07-09
**Core Value:** Otimização de prompts guiada por MCTS com um mecanismo de avaliação que efetivamente valide o comportamento da skill, garantindo código sustentável e modular.

## v1 Requirements

### Clean Code & Architecture (ARC)

- [x] **ARC-01**: Eliminar código morto (variáveis não utilizadas, funções órfãs, imports).
- [x] **ARC-02**: Reduzir a complexidade ciclomática de funções com múltiplos branches (if/else, nested loops).
- [x] **ARC-03**: Densificar o projeto garantindo que cada arquivo e módulo tenha uma responsabilidade isolada e clara.

### Judge Behavior (JUD)

- [x] **JUD-01**: Alterar o `AvaliadorDeSkill` para rodar no "Modo B" (Caça-Defeitos), forçando o modelo a identificar quebras de regras comportamentais antes de elogiar a estética.
- [x] **JUD-02**: O pipeline do DriftGate (`drift_monitor.py`) deve interpretar as reprovações do Modo B de maneira consistente, sem quebrar os limites de threshold atuais de rejeição.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Alteração da lógica MCTS | O foco da refatoração é limpeza de código e atualização do juiz. O núcleo MCTS atual (UCT, exploração/explotação) está funcionando adequadamente. |
| Quebra de endpoints de API | A API (FastAPI) deve ser transparente para os clientes. Qualquer alteração deve manter retrocompatibilidade nos requests/responses. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARC-01 | Phase 1 | Complete |
| ARC-02 | Phase 1 | Complete |
| ARC-03 | Phase 1 | Complete |
| JUD-01 | Phase 2 | Complete |
| JUD-02 | Phase 2 | Complete |

**Coverage:**

- v1 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-09 after initial definition*
