# Phase 3 Discussion Log

**Date:** 2026-07-09

## Q1: Target of Optimization (teleprompter.py)
**Options presented:**
- [x] (Recommended) Opção A: Migrar totalmente o Teleprompter para compilar o AvaliadorModoB. (O juiz otimizado passará a caçar defeitos com Few-Shot).
- [ ] Opção B: Voltar o gate (medir_drift) para avaliar o Modo A durante a compilação, mantendo o Modo B apenas como ferramenta secundária.

**Selection:** Opção A
**Notes:** O Teleprompter será refatorado para usar o `AvaliadorModoB` por padrão e gerar arquivos `avaliador_modo_b_otimizado.json`. Isso alinha a compilação ao novo portão (DriftGate) que já testa no Modo B.

## Q2: Reward Function Target (optimizer.py)
**Options presented:**
- [x] (Recommended) Opção A: Usar o Modo B para a recompensa. (O MCTS otimizará skills para não terem contradições, focando na resiliência e não só em estética).
- [ ] Opção B: Usar um mix (O MCTS recebe feedback do Modo A para estética e Modo B como pênalti/veto). Mais complexo de implementar.
- [ ] Opção C: Manter a recompensa no Modo A, mas usar o Modo B apenas no DriftGate. (Isso pode causar skills aprovadas pelo MCTS mas barradas no gate).

**Selection:** Opção A
**Notes:** A função de recompensa MCTS em `signatures.py` passa a depender do `AvaliadorModoB`, garantindo que os ramos escolhidos minimizem os "defeitos encontrados".
