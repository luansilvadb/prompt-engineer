# Research: Phase 3 - Close gap: JUD-01, JUD-02 Fix optimizer.py to target Mode B

## Objective
Corrigir a quebra de integração introduzida na Fase 2, garantindo que o ecossistema (MCTS no `optimizer.py` e o compilador no `teleprompter.py`) passe a usar e mirar o `AvaliadorModoB` (Modo B - Caça-Defeitos) ao invés do Modo A.

## Files Investigated

### 1. `src/teleprompter.py`
- **Current State:** O processo de BootstrapFewShot atualmente importa e compila `AvaliadorDeSkill` (Modo A), salvando-o como `avaliador_modo_a_otimizado.json`.
- **Required Changes:**
  - Importar `AvaliadorModoB` de `src.signatures`.
  - Substituir o módulo que será compilado: de `avaliador_module = dspy.Predict(AvaliadorDeSkill)` para `avaliador_module = dspy.Predict(AvaliadorModoB)`.
  - Atualizar as referências de salvamento: alterar os paths de `avaliador_modo_a_otimizado.json` para `avaliador_modo_b_otimizado.json` (incluindo as variáveis `out_path`, `candidate_path` e `bak_path`).

### 2. `src/signatures.py`
- **Current State:** A `funcao_de_recompensa` chama `_invoke_judge` (que aciona o Modo A) e retorna o score com `resultado.feedback_detalhado`.
- **Required Changes:**
  - Atualizar `funcao_de_recompensa` para chamar o avaliador no Modo B usando `_invoke_judge_modo_b_with(avaliador_modo_b_module, exemplo, predicao)`.
  - Modificar a construção do feedback retornado para o MCTS: deve focar exclusivamente nos "defeitos encontrados" (formatando como lista, se houver) para forçar as mutações a focar na correção de falhas e contradições. Caso não existam defeitos, pode retornar o feedback detalhado tradicional.
  - O score (oriundo de `_calculate_score`) deve ser penalizado caso defeitos sejam encontrados, garantindo a redução da nota com base nas quebras arquiteturais detectadas.

### 3. `src/optimizer.py`
- **Current State:** Importa `funcao_de_recompensa` de `src.signatures` e consome a tupla `(reward, feedback)`.
- **Required Changes:**
  - O comportamento se ajustará de forma automática às modificações de `funcao_de_recompensa`. A transição fluida do MCTS para tratar feedback baseado em falhas e notas penalizadas deve ocorrer sem necessidade de alterar as lógicas primárias de backpropagation ou expansão do otimizador, a não ser que ajustes em logs sejam desejáveis para maior clareza durante o output no CLI.

## Validation Architecture

To ensure the changes behave correctly per Nyquist Validation standards (Dimension 8), the following testing protocol will be enforced:

1. **Compiler Assertion:**
   - Executar `python -m src.teleprompter`.
   - **Expected:** O script deve rodar sem erros. O artefato gerado deve ser salvo no diretório `src/outputs/models` obrigatoriamente sob o nome `avaliador_modo_b_otimizado.json`. Nenhuma menção a "Modo A" deve surgir nos novos arquivos persistidos.

2. **MCTS & Reward Shaping Feedback Loop:**
   - Realizar um "dry-run" do otimizador em um dataset reduzido para simular chamadas de mutação.
   - **Expected:** Inspecionar o log (progress tracker) e confirmar que o prompt gerado para o agente reflete diretamente a lista de `defeitos_encontrados` provinda do Modo B, guiando de fato a mutação para o acerto comportamental.
   - **Expected:** A nota (Q-Value) deve refletir as penalizações impostas pelas contradições encontradas.

3. **Drift Monitor Compatibility (Regression):**
   - Garantir que a avaliação com Golden Set via `JudgeProbeRunner` consegue invocar e parsear candidatos corretamente em Modo B, mantendo a consistência cruzada estabelecida na Fase 2.
