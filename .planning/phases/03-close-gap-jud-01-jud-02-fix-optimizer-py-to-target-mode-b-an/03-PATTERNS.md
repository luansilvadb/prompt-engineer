# Patterns & Analogies: Phase 3

## Files to be Modified

### 1. `src/teleprompter.py`
- **Role:** Central script for compiling the DSPy evaluator (judge) using `BootstrapFewShot`.
- **Data Flow:** Loads high-reward experiences from `ExperienceStore` -> Formats into DSPy Examples -> Instantiates the judge module -> Compiles it using `BootstrapFewShot` -> Evaluates via `drift_monitor` -> Saves the compiled candidate to JSON.
- **Classification:** Pipeline Configuration / Compiler Script.
- **Existing Analog:** The file itself, which currently implements the exact same pipeline but targeted at `AvaliadorDeSkill` (Mode A).
- **Concrete Code Excerpts:**
  ```python
  # CURRENT STATE (Mode A)
  from src.signatures import AvaliadorDeSkill
  
  avaliador_module = dspy.Predict(AvaliadorDeSkill)
  
  out_path = output_dir / 'avaliador_modo_a_otimizado.json'
  candidate_path = output_dir / 'avaliador_modo_a_otimizado.candidate.json'
  bak_path = output_dir / 'avaliador_modo_a_otimizado.json.bak'
  ```
  ```python
  # PLANNED STATE (Mode B)
  from src.signatures import AvaliadorModoB
  
  avaliador_module = dspy.Predict(AvaliadorModoB)
  
  out_path = output_dir / 'avaliador_modo_b_otimizado.json'
  candidate_path = output_dir / 'avaliador_modo_b_otimizado.candidate.json'
  bak_path = output_dir / 'avaliador_modo_b_otimizado.json.bak'
  ```

### 2. `src/signatures.py`
- **Role:** Defines the data structures, DSPy signatures, and the reward function wrapper that interfaces with the MCTS loop in `optimizer.py`.
- **Data Flow:** `funcao_de_recompensa` receives an example and prediction -> Invokes the evaluator module to grade the generated prompt -> Checks critical rules -> Calculates a composite score -> Returns `(score, feedback)`.
- **Classification:** Reward Function / Integration Layer.
- **Existing Analog:** The `_invoke_judge_modo_b_with` function inside the same file already properly invokes the Mode B evaluator and parses `defeitos_encontrados`. `funcao_de_recompensa` acts as the integration point that needs to be rerouted to this Mode B invocation.
- **Concrete Code Excerpts:**
  ```python
  # CURRENT STATE (funcao_de_recompensa - Mode A)
  def funcao_de_recompensa(exemplo, predicao, trace=None):
      try:
          resultado = _invoke_judge(exemplo, predicao)
          
          if not _check_critical_rules(resultado):
              return 0.0, resultado.feedback_detalhado
              
          score = _calculate_score(resultado)
          return score, resultado.feedback_detalhado
      except Exception as e:
          return 0.0, f'Erro interno na avaliação: {str(e)}'
  ```
  ```python
  # PLANNED STATE (funcao_de_recompensa - Mode B)
  def funcao_de_recompensa(exemplo, predicao, trace=None):
      try:
          # Use Mode B module instead of Mode A wrapper
          resultado = _invoke_judge_modo_b_with(avaliador_modo_b_module, exemplo, predicao)
          
          if not _check_critical_rules(resultado):
              return 0.0, resultado.feedback_detalhado
              
          score = _calculate_score(resultado)
          
          # Prioritize structural defects in the feedback and penalize the score
          if resultado.defeitos_encontrados:
              # Example structural penalty
              penalty = len(resultado.defeitos_encontrados) * 0.1
              score = max(0.0, score - penalty)
              
              feedback = "DEFEITOS E CONTRADIÇÕES ENCONTRADAS:\n" + \
                         "\n".join(f"- {d}" for d in resultado.defeitos_encontrados) + \
                         "\n\nCorrija as quebras arquiteturais acima urgentemente."
          else:
              feedback = resultado.feedback_detalhado
              
          return score, feedback
      except Exception as e:
          return 0.0, f'Erro interno na avaliação: {str(e)}'
  ```

### 3. `src/optimizer.py`
- **Role:** Main MCTS loop execution.
- **Data Flow:** Imports `funcao_de_recompensa` from `src.signatures` -> Uses the returned score for backpropagation and the feedback to construct mutation prompts.
- **Classification:** Core Logic / Control Flow.
- **Existing Analog:** N/A - The design explicitly plans for this file to adapt automatically.
- **Notes:** According to `RESEARCH.md`, the behavior of the optimizer will adjust dynamically based on the changes in `funcao_de_recompensa` (which will now penalize scores and focus feedback on defects). No primary logic modifications are required here, meaning the codebase follows a well-decoupled pattern where the reward shaping is fully contained in `signatures.py`.
