---
wave: 1
depends_on: []
files_modified:
  - src/heuristic_evaluator.py
  - src/config.py
  - src/optimizer.py
  - tests/test_heuristic_evaluator.py
  - tests/conftest.py
  - tests/test_optimizer.py
  - requirements.txt
autonomous: true
---

# Phase 05: Avaliador de Profundidade Heurística Plan

## Tasks

<task>
<read_first>
- requirements.txt
</read_first>
<action>
Modify or create `requirements.txt` in the root directory.
Add the line `textstat` to ensure the library is tracked and installed in all environments automatically.
</action>
<acceptance_criteria>
`requirements.txt` contains `textstat`.
</acceptance_criteria>
</task>

<task>
<read_first>
- tests/conftest.py
</read_first>
<action>
Create or modify `tests/conftest.py` to establish the required Test Fixtures for Verbosidade and Mocking Infrastructure.
1. Add a pytest fixture named `mock_heavy_evaluators` that patches `src.ausculta_modo_b.AvaliadorModoB` and `sentence_transformers.SentenceTransformer` (or any equivalent embeddings used) so they do not make live network calls during tests.
2. Add a pytest fixture named `sample_verbose_text` that returns a large, highly verbose text string for testing Layer 2 penalties.
3. Add a pytest fixture named `sample_short_text` that returns a short, direct text string.
</action>
<acceptance_criteria>
`tests/conftest.py` contains fixtures `mock_heavy_evaluators`, `sample_verbose_text`, and `sample_short_text` with mock patches for heavy evaluators.
</acceptance_criteria>
</task>

<task>
<read_first>
- .planning/phases/05-avaliador-de-profundidade-heur-stica/05-PATTERNS.md
</read_first>
<action>
Create `src/heuristic_evaluator.py` that implements Layer 1 and Layer 2 text heuristics.
Include `import textstat` and `import re`. Set language to Portuguese: `textstat.set_lang('pt')`.
Define the function `evaluate_heuristics(text: str, density_min: float = 0.35, penalty_factor: float = 0.85) -> dict`.
Implementation logic:
- If `textstat.lexicon_count(text)` < 30, return `{"prune": False, "penalty_multiplier": 1.0, "reason": "Bypassed (short text)"}`.
- Layer 1 (Lexical Density): Calculate unique_ratio as `len(set(tokens)) / max(1, len(tokens))` where tokens are words from `text.lower()` with punctuation removed (using `re.sub(r'[^\w\s]', '', text.lower())`). If `unique_ratio < density_min`, return `{"prune": True, "penalty_multiplier": 0.0, "reason": "Low Lexical Density"}`.
- Layer 2 (Readability): Calculate `reading_ease = textstat.flesch_reading_ease(text)`. If word count > 200 and `reading_ease > 80`, multiplier is `penalty_factor`, else 1.0. Return `{"prune": False, "penalty_multiplier": multiplier, "reason": "Passed"}`.
</action>
<acceptance_criteria>
`src/heuristic_evaluator.py` exists and contains the function `def evaluate_heuristics(text: str, density_min: float = 0.35, penalty_factor: float = 0.85) -> dict:`
</acceptance_criteria>
</task>

<task>
<read_first>
- src/config.py
</read_first>
<action>
Modify `src/config.py`. Locate the `get_mcts_config()` function.
Add two new keys to the returned dictionary:
- `'lexical_density_min': float(os.environ.get('MCTS_LEXICAL_DENSITY_MIN', '0.35'))`
- `'verbosity_penalty_factor': float(os.environ.get('MCTS_VERBOSITY_PENALTY_FACTOR', '0.85'))`
</action>
<acceptance_criteria>
`src/config.py` contains the exact strings `'lexical_density_min':` and `'verbosity_penalty_factor':` inside the `get_mcts_config` dictionary.
</acceptance_criteria>
</task>

<task>
<read_first>
- src/optimizer.py
- src/heuristic_evaluator.py
</read_first>
<action>
Modify `src/optimizer.py`.
1. Add `from src.heuristic_evaluator import evaluate_heuristics` at the top of the file.
2. In `Optimizer.__init__`, read config values: add `self.lexical_density_min = config.get('lexical_density_min', 0.35)` and `self.verbosity_penalty_factor = config.get('verbosity_penalty_factor', 0.85)`.
3. In `Optimizer._run_mcts_iteration`, intercept the flow BEFORE `reward, feedback = self.simulation(child.instruction)`.
4. Call `heuristic_result = evaluate_heuristics(child.instruction, density_min=self.lexical_density_min, penalty_factor=self.verbosity_penalty_factor)`.
5. Check if `heuristic_result.get("prune")` is True. If so:
   - Use `self.on_progress` to log `f"    [Poda Heurística] {heuristic_result.get('reason')}"`.
   - Set `child.feedback = heuristic_result.get("reason")`.
   - Set `child.last_reward = 0.0`.
   - Call `self.backpropagation(child, 0.0)`.
   - Return `False, False, 0.0` immediately.
6. If NOT pruned, allow the existing `reward, feedback = self.simulation(child.instruction)` to run.
7. After `simulation`, extract `multiplier = heuristic_result.get("penalty_multiplier", 1.0)`.
8. Apply the multiplier: `reward = reward * multiplier`. If `multiplier < 1.0`, log `f"    [Penalidade Heurística] Fator de decaimento: {multiplier:.2f}"` via `self.on_progress`.
</action>
<acceptance_criteria>
`src/optimizer.py` contains `evaluate_heuristics` call inside `_run_mcts_iteration` and short-circuits with `self.backpropagation(child, 0.0)` if pruned.
</acceptance_criteria>
</task>

<task>
<read_first>
- src/heuristic_evaluator.py
</read_first>
<action>
Create `tests/test_heuristic_evaluator.py`.
Import `evaluate_heuristics` from `src.heuristic_evaluator`.
Write three pytest functions:
- `test_short_text_bypass()`: Test with short text (e.g., "Curto e direto."). Assert `result["prune"]` is False and multiplier is 1.0.
- `test_low_lexical_density_prune()`: Test with hollow verbosity: "palavra " * 100. Assert `result["prune"]` is True and multiplier is 0.0.
- `test_layer_2_penalty()`: Test with text > 200 words and high reading ease (e.g., "O gato senta no tapete macio e dorme bem " * 30). Assert `result["prune"]` is False and `result["penalty_multiplier"] < 1.0`.
</action>
<acceptance_criteria>
`pytest tests/test_heuristic_evaluator.py` runs successfully and passes all 3 tests.
</acceptance_criteria>
</task>

<task>
<read_first>
- src/optimizer.py
- tests/test_optimizer.py
</read_first>
<action>
Create or modify `tests/test_optimizer.py` to add integration tests for the MCTS pipeline.
Write two pytest functions utilizing the test fixtures:
- `test_optimizer_layer1_hard_pruning(mock_heavy_evaluators)`: Configure MCTS child node text to trigger Layer 1 pruning (e.g., low lexical density). Assert that `evaluate_heuristics` prunes the evaluation and the mocked heavy evaluators are NOT called.
- `test_optimizer_layer2_penalty_multiplier(mock_heavy_evaluators, sample_verbose_text)`: Configure MCTS child node with verbose text. Assert that the optimizer calculates the reward correctly scaled by the `verbosity_penalty_factor` and does not prune.
</action>
<acceptance_criteria>
`pytest tests/test_optimizer.py` runs successfully and verifies that Layer 1 hard pruning skips heavy evaluation and Layer 2 correctly scales the final reward.
</acceptance_criteria>
</task>

## Verification

- [ ] Ensure `textstat` is installed in the local environment (run `pip install textstat` if needed).
- [ ] Run `pytest tests/test_heuristic_evaluator.py` and ensure the tests pass.
- [ ] Run `pytest tests/test_optimizer.py` to verify integration tests for MCTS pipeline pass.
- [ ] Run `python -m pytest` on the full test suite to ensure `optimizer.py` changes do not break existing functionality.

## Must Haves

truths:
  - D-01: A estratégia de penalização atua em duas camadas (hard prune e redução progressiva).
  - D-02: Utiliza-se uma abordagem combinada (Densidade Lexical e métricas do Textstat).
  - D-03: As heurísticas lexicais atuam de forma sequencial como filtro primário ANTES da avaliação pesada.
  - `textstat` is successfully integrated and `textstat.set_lang('pt')` is configured globally in `heuristic_evaluator.py`.
  - Heavy evaluation (LLM/embeddings) is skipped for hard-pruned branches in MCTS.
  - Existing tests must not fail due to the new heuristic interception.

## Artifacts this phase produces

- `src/heuristic_evaluator.py`
- `tests/test_heuristic_evaluator.py`
- `tests/conftest.py`
- `tests/test_optimizer.py`
- `requirements.txt`
- `evaluate_heuristics`
- `'lexical_density_min'`
- `'verbosity_penalty_factor'`
- `Optimizer.lexical_density_min`
- `Optimizer.verbosity_penalty_factor`
