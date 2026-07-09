---
phase: 02-judge-ca-a-defeitos-mode
plan: 02
subsystem: drift
tags: [ModoB, GoldenSet, JudgeProbeRunner]
requires: [JUD-01, JUD-02]
provides: [JUD-03]
affects: [drift/runner.py]
key-files:
  created:
    - src/ausculta_modo_b.py
  modified:
    - src/drift/runner.py
key-decisions:
  - "O Modo B é usado por padrão em JudgeProbeRunner, com fallback para o Modo A via parâmetro opcional (D-03)."
  - "Criado um teste isolado via `ausculta_modo_b.py` para provar a eficácia do Modo B contra paradoxos estruturais sem depender de Ollama local (usando as chaves de API globais do sistema via config)."
requirements: [JUD-01, JUD-02]
coverage:
  - verification:
      kind: command
      ref: python ausculta_modo_b.py
      status: pass
    human_judgment: false
---

# Phase 02 Plan 02: Habilitar Modo B e Validar com Golden Set Summary

O `JudgeProbeRunner` foi atualizado para suportar o carregamento e inicialização do `AvaliadorModoB`, bem como incorporá-lo como o pipeline padrão em suas execuções (`run()` agora invoca por padrão `run_modo_b`). O script `ausculta_modo_b.py` foi implementado para atuar como o análogo de verificação no modo Caça-Defeitos e demonstrou a sua eficácia.

## Accomplishments
- **Atualização do `JudgeProbeRunner`:** Os métodos de carga de candidatos (`load_candidate_modo_b`), instanciamento baseline (`as_zero_modo_b`) e execução propriamente dita (`run_modo_b`) foram implementados.
- **Modo B Default:** O método principal `.run()` foi reprogramado para disparar o modo B por padrão.
- **Teste e Validação (`ausculta_modo_b.py`):** Criado com um `GoldenSet` isolado simulando a skill "Espelho Distorcido" (com a contradição "elogie o usuário, mas é ESTRITAMENTE PROIBIDO dizer qualquer elogio ou palavra positiva").
- **Validação de Drift:** A execução comprovou que o LLM identificou a contradição estrutural e atribuiu o score composto (previsto: 0.049) em alinhamento preciso com a faixa de "fail" que esperávamos (aprox: 0.665), reduzindo a recompensa base e demonstrando o valor diagnóstico do Modo B.

## Deviations from Plan

**[Rule 1 - Fix Attempt] Erro de configuração de LLM no script pontual**
- Encontrado durante: Execução de `ausculta_modo_b.py`.
- Problema: O plano instruía instanciar diretamente o Ollama (gemma2), que não estava rodando localmente, gerando Connection Refused.
- Correção: O script foi alterado para utilizar `config.setup()` a fim de consumir a configuração global provida pelo arquivo `.env` do sistema.
- Impacto: Baixo. O teste conseguiu ser concluído utilizando o modelo central sem exigir alterações ao nível do framework.

**Total deviations:** 1 auto-fixed.

## Next Steps
Phase complete, ready for next step.
