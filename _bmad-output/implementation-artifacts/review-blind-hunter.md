# Blind Hunter Review Prompt

Invoke the `bmad-review-adversarial-general` skill on this diff:

```
diff --git a/src/domain/config.py b/src/domain/config.py
--- a/src/domain/config.py
+++ b/src/domain/config.py
@@ -38,28 +38,48 @@ class MCTSConfig:

     def __post_init__(self) -> None:
-        if self.selection_policy not in ("puct", "ucb1_tuned", "ucb1"):
-            raise ValueError(...)
-        if not (0.0 < self.gamma <= 1.0):
-            raise ValueError(...)
-        ... (10 inline validations)
+        _validate_selection_policy(self.selection_policy)
+        _validate_bounds(self.gamma, self.c_param, self.progressive_c)
+        _validate_thresholds(self.progressive_alpha, self.value_threshold, self.max_iterations)
+        _validate_density(self.density_multiplier_min, self.density_multiplier_max)
+        _validate_root_samples(self.root_median_samples)
+
+# 5 new module-level validation functions added after MCTSConfig

diff --git a/src/domain/mcts.py b/src/domain/mcts.py
--- a/src/domain/mcts.py
+++ b/src/domain/mcts.py
@@ -1,5 +1,6 @@
 import re  # added at module level (was inline import)

-    # _normalize_key had inline fence stripping + blank line collapse (CC=12)
+    # Now delegates to _strip_markdown_fences() and _collapse_blank_lines() (CC=3)
+    # Two new module-level helper functions added

diff --git a/src/optimizer.py b/src/optimizer.py
--- a/src/optimizer.py
+++ b/src/optimizer.py
@@ +3 module-level pruning helpers restored:
+   _check_lexical_critical(instruction) -> bool
+   _check_density_critical(instruction, ref_instruction, mutation_strategy) -> bool
+   _check_semantic_critical(instruction, parent_instruction) -> bool

-    _should_prune: inline density/semantic checks replaced with calls to above helpers

+    4 MCTS iteration helpers extracted from _run_mcts_iteration:
+    _is_cancelled(self) -> bool
+    _expand_child(self, leaf) -> MCTSNode
+    _apply_reward_multipliers(self, reward, heuristic_result, child) -> float
+    _commit_iteration(self, child, reward, feedback) -> None

-    _run_mcts_iteration: CC 19 → 9. Inline expansion, multiplier application,
     and backprop+persist code replaced with helper calls.

-    _run_threaded_search: race condition fix — consecutive_zeros read protected
     by self.lock before passing to _run_single_iteration.

diff --git a/src/routers/jobs.py b/src/routers/jobs.py
--- a/src/routers/jobs.py
+++ b/src/routers/jobs.py
@@ +_drain_pending_events(job) — extracts initial queue drain from _live_event_generator
@@ +_try_consume_event(job) — extracts event consumption with timeout/cancel handling
-    _live_event_generator: CC 12 → 10. Drain and consume logic delegated to helpers.
```

The full diff is at `_bmad-output/implementation-artifacts/review-diff.txt`.
