# Edge Case Hunter Review Prompt

Invoke the `bmad-review-edge-case-hunter` skill on this diff:

```
Changes made to fix 6 bugs found in post-refactor audit:

1. optimizer.py: Re-extracted _is_cancelled, _expand_child, _apply_reward_multipliers,
   _commit_iteration from _run_mcts_iteration (were silently inlined in commit ffcead7).
   _run_mcts_iteration CC 19 → 9.

2. optimizer.py: Re-extracted _check_lexical_critical, _check_density_critical,
   _check_semantic_critical as module-level pure functions (were inlined in _should_prune,
   violating KEEP instruction from spec change log). _should_prune CC 11 → 10.

3. optimizer.py: Fixed race condition in _run_threaded_search — consecutive_zeros was
   read by all threads outside the lock before any thread could update it. Now reads
   inside self.lock before passing to _run_single_iteration.

4. routers/jobs.py: Extracted _drain_pending_events and _try_consume_event from
   _live_event_generator. CC 12 → 10.

5. domain/config.py: Extracted 5 validation helpers from MCTSConfig.__post_init__.
   CC 12 → 1.

6. domain/mcts.py: Extracted _strip_markdown_fences and _collapse_blank_lines from
   TranspositionTable._normalize_key. CC 12 → 3. import re moved to module level.

All 269 tests pass. radon cc confirms all targeted functions ≤ 10.
```

The full diff is at `_bmad-output/implementation-artifacts/review-diff.txt`.
