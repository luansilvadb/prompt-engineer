# Phase 3: Close gap: JUD-01, JUD-02 Fix optimizer.py to target Mode B and align teleprompter with medir_drift - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Corrigir a quebra de integração introduzida na Fase 2, garantindo que todo o ecossistema (MCTS no `optimizer.py` e o compilador no `teleprompter.py`) passe a usar e mirar o `AvaliadorModoB` (Modo B - Caça-Defeitos) ao invés do Modo A.

</domain>

<decisions>
## Implementation Decisions

### Target of Optimization (teleprompter.py)
- **D-01:** O Teleprompter será totalmente migrado para compilar o `AvaliadorModoB`. Assim, o juiz otimizado passará a focar na identificação de contradições (Modo B) no regime Few-Shot. 

### Reward Function Target (optimizer.py)
- **D-02:** A função de recompensa do MCTS (`funcao_de_recompensa` e `_invoke_judge`) usará o Modo B. Com isso, o algoritmo MCTS priorizará a criação de skills que evitam contradições comportamentais e paradoxos estruturais (resiliência), em vez de apenas otimização estética.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planejamento e Requisitos
- `.planning/ROADMAP.md` — Goal do Milestone v1.0 e Fase 3.
- `.planning/REQUIREMENTS.md` — Requisitos JUD-01 e JUD-02.
- `.planning/v1.0-MILESTONE-AUDIT.md` — Relatório de auditoria que apontou a quebra de integração cruzada (Phase 2 → Phase 2).
- `.planning/phases/02-judge-ca-a-defeitos-mode/02-CONTEXT.md` — Contexto da Fase 2 (onde as regras do Modo B foram definidas originalmente).

### Arquivos Core a Alterar
- `src/teleprompter.py` — Script responsável pela compilação DSPy BootstrapFewShot.
- `src/signatures.py` — Onde `funcao_de_recompensa` e `_invoke_judge` estão localizadas.
- `src/optimizer.py` — O otimizador principal.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AvaliadorModoB` e `AvaliacaoModoB` (já implementados na Fase 2 em `signatures.py`): serão os novos alvos padrão.
- `medir_drift` (em `drift/metrics.py`) e `JudgeProbeRunner` (em `drift/runner.py`): já possuem suporte para avaliação no Modo B (Modo B é default nas medições).

### Established Patterns
- **Módulos isolados:** A injeção de classes mantém a estrutura intacta, mas precisamos alterar as chamadas originais de `AvaliadorDeSkill` para `AvaliadorModoB` no teleprompter e na recompensa MCTS.

### Integration Points
- **`teleprompter.py` (L71):** `avaliador_module = dspy.Predict(AvaliadorDeSkill)` deve mudar para `AvaliadorModoB`. Os paths de salvamento precisam ser ajustados para `avaliador_modo_b_otimizado.json`.
- **`signatures.py` (funcao_de_recompensa):** deve chamar `_invoke_judge_modo_b_with` ao invés da versão base (Modo A).

</code_context>

<specifics>
## Specific Ideas

- **Consistência do MCTS:** Ao usar o Modo B para recompensa, o feedback do MCTS deve focar exclusivamente nos "defeitos encontrados" (reduzindo a nota com base neles). O `calcular_composite` já suporta o peso dessas punições, mas garantir que a transição ocorra de maneira fluída é essencial para que a árvore MCTS continue avançando corretamente.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-close-gap-jud-01-jud-02-fix-optimizer-py-to-target-mode-b-an*
*Context gathered: 2026-07-09*
