# Phase 4: Avaliador de Profundidade Semântica - Implementation Patterns

**Mapped:** 2026-07-10
**Goal:** Define concrete code patterns for the semantic depth penalty using `sentence-transformers`.

## Files to Modify / Create

### 1. `src/semantic_evaluator.py` (Create)
- **Role:** Utility Module / Global Singleton
- **Data Flow:** Receives two strings (candidate and parent instructions) and optionally a threshold. Embeds both using the PyTorch-based global model, calculates cosine similarity, applies quadratic decay if similarity > threshold, and returns a penalty factor between `0.01` and `1.0`. 
- **Closest Analog:** Standard utility module with module-level variables for singleton behavior (simpler than a full class, avoiding overhead).
- **Code Pattern Excerpt:**
  ```python
  import torch
  from sentence_transformers import SentenceTransformer, util

  # Global singleton to avoid reloading the model
  _embedder = None

  def get_embedder():
      global _embedder
      if _embedder is None:
          _embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
      return _embedder

  def calculate_semantic_penalty(text1: str, text2: str, threshold: float = 0.85) -> float:
      model = get_embedder()
      
      # Truncate string sizes to prevent OOM (Security Domain requirement)
      text1 = text1[:2048]
      text2 = text2[:2048]
      
      emb1 = model.encode(text1, convert_to_tensor=True)
      emb2 = model.encode(text2, convert_to_tensor=True)
      
      # Extract scalar to avoid memory leaks in the MCTS loop
      cosine_sim = util.cos_sim(emb1, emb2).item()
      
      if cosine_sim <= threshold:
          return 1.0 # No penalty
          
      # Quadratic decay mapping [threshold, 1.0] -> [1.0, 0.0]
      penalty = 1.0 - ((cosine_sim - threshold) / (1.0 - threshold)) ** 2
      return max(0.01, float(penalty))
  ```

### 2. `src/optimizer.py` (Modify)
- **Role:** MCTS Engine (Core)
- **Data Flow:** Integrates the semantic penalty inside `_run_mcts_iteration`. Modifies the raw `reward` obtained from the LLM evaluator (`funcao_de_recompensa`) by multiplying it with the calculated penalty before applying the Delta Reward Shaping.
- **Closest Analog:** Existing reward modifiers like `calcular_delta_reward`.
- **Code Pattern Excerpt:**
  ```python
  from src.semantic_evaluator import calculate_semantic_penalty

  # Inside Optimizer.__init__:
  self.semantic_sim_threshold = config.get('semantic_sim_threshold', 0.85)

  # Inside Optimizer._run_mcts_iteration:
  reward, feedback = self.simulation(child.instruction)
  
  # --- SEMANTIC PENALTY ---
  parent_instruction = child.parent.instruction if child.parent else child.instruction
  penalty = calculate_semantic_penalty(
      child.instruction, 
      parent_instruction, 
      threshold=self.semantic_sim_threshold
  )
  if penalty < 1.0:
      self.on_progress(f"    [Penalidade Semântica] Fator de decaimento: {penalty:.2f}")
  reward = reward * penalty
  # ------------------------

  child.feedback = feedback
  child.last_reward = reward
  ```

### 3. `src/config.py` (Modify)
- **Role:** Configuration Management
- **Data Flow:** Loads `MCTS_SEMANTIC_SIM_THRESHOLD` from environment variables, defaulting to `0.85`, to be consumed by `optimizer.py`.
- **Closest Analog:** The `get_mcts_config` dictionary keys.
- **Code Pattern Excerpt:**
  ```python
  def get_mcts_config() -> dict:
      # ... existing configs ...
      
          # Limiar de penalidade de similaridade semântica (> 0.85 inicia decaimento)
          'semantic_sim_threshold': float(os.environ.get('MCTS_SEMANTIC_SIM_THRESHOLD', '0.85')),
      }
  ```

### 4. `tests/test_semantic_evaluator.py` (Create)
- **Role:** Unit Tests
- **Data Flow:** Test suite defining test cases for the `semantic_evaluator.py` functionality based on Phase 4 requirements.
- **Closest Analog:** Standard `pytest` test suite.
- **Code Pattern Excerpt:**
  ```python
  import pytest
  from src.semantic_evaluator import calculate_semantic_penalty, get_embedder

  def test_singleton_loading():
      embedder1 = get_embedder()
      embedder2 = get_embedder()
      assert embedder1 is embedder2

  def test_no_penalty():
      text1 = "A completely different concept for testing."
      text2 = "Another unrelated string that has no semantic similarity whatsoever."
      penalty = calculate_semantic_penalty(text1, text2)
      assert penalty == 1.0

  def test_continuous_decay():
      # Should trigger decay between 0.01 and 1.0
      text1 = "Resolva esta equação de segundo grau."
      text2 = "Resolva esta equação do segundo grau."
      penalty = calculate_semantic_penalty(text1, text2)
      assert 0.01 <= penalty < 1.0

  def test_max_penalty():
      text = "This is a strictly identical text used for testing."
      penalty = calculate_semantic_penalty(text, text)
      assert penalty == 0.01
  ```
