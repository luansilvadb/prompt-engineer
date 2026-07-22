# Edge Case Hunter Review Prompt

Invoke the `bmad-review-edge-case-hunter` skill on the diff in `_bmad-output/implementation-artifacts/review-diff.txt`.

Context: This is a codebase refactoring that extracted helper functions from high-CC functions. Key extractions:
- teleprompter.py: `_safe_get`, `_check_manteve_regras`, `_check_defeitos`, `_check_feedback`, `_check_nota`, optimizer factories
- context_audit.py: 7 criterion evaluators extracted from one monolithic function
- optimizer.py: `_is_cancelled`, `_expand_child`, `_apply_reward_multipliers`, `_commit_iteration`, `_select_fallback_strategy`, `_is_candidate_valid`, `_register_child_node`
- jobs.py: `_is_job_orphan`, `_is_job_done`

Walk every branching path in the changed functions and identify unhandled edge cases: None inputs, empty strings, boundary values, exception propagation, lock ordering, thread safety.
