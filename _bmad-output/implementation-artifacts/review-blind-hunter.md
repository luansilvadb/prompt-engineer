# Blind Hunter Review Prompt

Invoke the `bmad-review-adversarial-general` skill on the diff in `_bmad-output/implementation-artifacts/review-diff.txt`.

Context: This is a codebase refactoring that:
1. Decomposed high cyclomatic complexity functions (CC 41→2, 32→8, 21→9, 17→10)
2. Removed dead code (IAvaliadorDeSkill protocol, unused variables)
3. Verified no behavior changes — 101 tests pass

The diff covers: src/teleprompter.py, src/context_audit.py, src/optimizer.py, src/routers/jobs.py, src/domain/agent_interfaces.py

Look for: subtle behavioral changes, broken invariants, incorrect extractions, logic reversals, missing edge cases introduced by the refactoring.
