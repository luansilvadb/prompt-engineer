# Phase 05: Avaliador de Profundidade Heurística - Implementation Patterns

**Mapped:** 2026-07-10
**Goal:** Define concrete code patterns for real-time penalty of "hollow verbosity" using `textstat` heuristics.

## Files to Modify / Create

### 1. `src/heuristic_evaluator.py` (Create)
- **Role:** Utility Module
- **Data Flow:** Evaluates lexical density (Layer 1) and readability complexity (Layer 2) of a candidate string. Returns a dictionary containing a `prune` boolean for early termination and a `penalty_multiplier` for reward shaping.
- **Closest Analog:** `src/semantic_evaluator.py` (acts as a standalone string evaluator).
- **Code Pattern Excerpt:**
  ```python
  import textstat
  import re

  # Configurável por variáveis de ambiente via config.py (D-02)
  # Default language setup to support PT-BR inputs avoiding Pitfall 1.
  textstat.set_lang('pt')

  def evaluate_heuristics(text: str, density_min: float = 0.35, penalty_factor: float = 0.85) -> dict:
      """
      Evaluates text and returns whether it should be hard-pruned (Layer 1)
      and what its penalty multiplier should be (Layer 2).
      """
      word_count = textstat.lexicon_count(text)
      
      # Short texts bypass filters
      if word_count < 30:
          return {"prune": False, "penalty_multiplier": 1.0, "reason": "Bypassed (short text)"}
          
      # Layer 1: Lexical Density (Type-Token Ratio)
      clean_text = re.sub(r'[^\w\s]', '', text.lower())
      tokens = clean_text.split()
      unique_ratio = len(set(tokens)) / max(1, len(tokens))
      
      # Hard prune if highly repetitive (hollow verbosity)
      if unique_ratio < density_min:
          return {"prune": True, "penalty_multiplier": 0.0, "reason": "Low Lexical Density"}
          
      # Layer 2: Readability combined penalty
      # Penalize if it's very long but very simple (high Flesch Reading Ease means easy)
      reading_ease = textstat.flesch_reading_ease(text)
      
      multiplier = 1.0
      if word_count > 200 and reading_ease > 80:
          # Long and overly simple text gets penalized
          multiplier = penalty_factor
          
      return {"prune": False, "penalty_multiplier": multiplier, "reason": "Passed"}
  ```

### 2. `src/optimizer.py` (Modify)
- **Role:** MCTS Engine (Core)
- **Data Flow:** Integrates `evaluate_heuristics` at the start of `_run_mcts_iteration`. If the heuristics dictate a prune, it immediately bypasses LLM and semantic evaluation, backpropagating zero reward. Otherwise, it applies the heuristic penalty multiplier to the final simulation reward.
- **Closest Analog:** Existing semantic similarity penalty integration.
- **Code Pattern Excerpt:**
  ```python
  from src.heuristic_evaluator import evaluate_heuristics

  # Inside Optimizer.__init__:
  self.lexical_density_min = config.get('lexical_density_min', 0.35)
  self.verbosity_penalty_factor = config.get('verbosity_penalty_factor', 0.85)

  # Inside Optimizer._run_mcts_iteration:
  # ... (node expansion logic)

  # --- HEURISTIC PENALTY (Layer 1 & 2) ---
  heuristic_result = evaluate_heuristics(
      child.instruction, 
      density_min=self.lexical_density_min,
      penalty_factor=self.verbosity_penalty_factor
  )

  if heuristic_result.get("prune"):
      self.on_progress(f"    [Poda Heurística] {heuristic_result.get('reason')}")
      child.feedback = heuristic_result.get("reason")
      child.last_reward = 0.0
      # Backpropagate zero reward and skip heavy evaluation
      self.backpropagation(child, 0.0)
      return False, False, 0.0
  # ----------------------------------------

  # Run heavy evaluation
  reward, feedback = self.simulation(child.instruction)

  # --- HEURISTIC MULTIPLIER (Layer 2) ---
  multiplier = heuristic_result.get("penalty_multiplier", 1.0)
  if multiplier < 1.0:
      self.on_progress(f"    [Penalidade Heurística] Fator de decaimento: {multiplier:.2f}")
  reward = reward * multiplier
  # --------------------------------------
  
  # ... (semantic penalty follows)
  ```

### 3. `src/config.py` (Modify)
- **Role:** Configuration Management
- **Data Flow:** Loads `MCTS_LEXICAL_DENSITY_MIN` and `MCTS_VERBOSITY_PENALTY_FACTOR` thresholds to be exposed to `optimizer.py`.
- **Closest Analog:** The `get_mcts_config` threshold additions.
- **Code Pattern Excerpt:**
  ```python
  def get_mcts_config() -> dict:
      # ... existing configs ...
      
          # Thresholds do Avaliador de Profundidade Heurística
          'lexical_density_min': float(os.environ.get('MCTS_LEXICAL_DENSITY_MIN', '0.35')),
          'verbosity_penalty_factor': float(os.environ.get('MCTS_VERBOSITY_PENALTY_FACTOR', '0.85')),
      }
  ```

### 4. `tests/test_heuristic_evaluator.py` (Create)
- **Role:** Unit Tests
- **Data Flow:** Tests `heuristic_evaluator.py` functions to ensure robust hard-pruning logic and correct threshold behavior without triggering external API calls.
- **Closest Analog:** `tests/test_semantic_evaluator.py` or standard `pytest` scripts.
- **Code Pattern Excerpt:**
  ```python
  import pytest
  from src.heuristic_evaluator import evaluate_heuristics

  def test_short_text_bypass():
      result = evaluate_heuristics("Curto e direto.")
      assert not result["prune"]
      assert result["penalty_multiplier"] == 1.0

  def test_low_lexical_density_prune():
      # Hollow verbosity (repetition)
      text = "palavra " * 100
      result = evaluate_heuristics(text)
      assert result["prune"]
      assert result["penalty_multiplier"] == 0.0

  def test_layer_2_penalty():
      # Simple and very long text
      # We need >200 words of easy text to trigger penalty
      text = "O gato senta no tapete macio e dorme bem " * 30
      result = evaluate_heuristics(text)
      assert not result["prune"]
      assert result["penalty_multiplier"] < 1.0
  ```
