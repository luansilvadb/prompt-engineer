# Optimizers (a.k.a. Teleprompters)

"Teleprompter" was the original (2023 paper) name — derived from automating prompting
"at a distance," without manual intervention. The current library still recognizes
the term internally/in some class names, but the public-facing, day-to-day name is
**optimizer**. When talking to someone reading the original paper, use
"teleprompter"; when talking about the current library, say "optimizer" (or note the
terminology shift explicitly if it matters to the conversation).

## What compiling means

Given a **program** (a DSPy module or composition of modules), a **training set**
(inputs are required; labels are only needed for whatever the metric checks — often
just the final output, not intermediate steps), and a **metric** (a scoring
function — can be as simple as exact-match or as complex as another DSPy program),
an optimizer's `.compile()` method returns a *new*, optimized copy of the program.
The original passed-in program is never mutated (`.compile()` always starts from
`student.reset_copy()`).

Historically (per the paper) this was framed as three stages: (1) candidate
generation — bootstrap demonstration traces per predictor by running the program (or
a teacher program) and keeping traces that pass the metric; (2) parameter
optimization — search over those candidates (random search, Bayesian optimization,
etc.); (3) higher-order program optimization — restructure control flow, e.g.
ensembling multiple compiled candidates. That framing is still a reasonable mental
model, though the current optimizer roster tunes a more explicit set of "knobs."

## The three knobs every optimizer turns

Every optimizer tunes one or more of:

- **Instructions** — the natural-language docstring/instruction on a predictor's
  signature.
- **Demonstrations** — the in-context few-shot examples a predictor sees.
- **Weights** — the underlying LM's parameters, when it's a tunable/finetunable
  model.

Picking the wrong optimizer for the actual bottleneck (e.g. running an
instruction-only optimizer when the real problem is that demos are missing) is one of
the most common practical mistakes — the debugging question to ask is "which of the
three knobs is actually starving this program?"

## Optimizer-by-optimizer (current, 2026 library)

**Baselines — try these first:**
- `LabeledFewShot(k=16)` — no LM calls at compile time; just samples up to `k`
  examples from the trainset as demos. The "is heavier optimization even worth it"
  sanity check.
- `BootstrapFewShot(metric, max_bootstrapped_demos=4, max_labeled_demos=16, ...)` —
  runs the program (or a supplied `teacher`) on training examples, keeps the traces
  that pass the metric as bootstrapped demos. The direct descendant of the paper's
  `BootstrapFewShot`, and still the safe first real optimizer to reach for.

**Search across demo sets:**
- `BootstrapFewShotWithRandomSearch` (alias `BootstrapRS`) — runs `BootstrapFewShot`
  many times with different seeds, evaluates each candidate on a validation set,
  keeps the best. This is the paper's `bootstrap×2` / random-search family,
  generalized.
- `KNNFewShot` — demos are chosen per-call at inference time via nearest-neighbor
  lookup against an embedded trainset, rather than fixed once at compile time. Did
  not exist at paper time.

**Optimize instructions:**
- `COPRO` — breadth-first search: proposes `breadth` candidate instructions per
  predictor at each of `depth` levels, keeps the best-scoring ones.
- `GEPA` — **reflective, evolutionary instruction search** (introduced July 2025).
  The only optimizer that reads `Prediction(score, feedback)` per predictor rather
  than a bare scalar — it threads natural-language critique from the metric into a
  `reflection_lm`'s proposals. Currently the go-to for prompt-only optimization when
  you have a feedback-rich metric. Did not exist at paper time; is the closest
  current analogue to the paper's aspiration for open-ended, non-hand-written prompt
  improvement.

**Optimize instructions and demos jointly:**
- `MIPROv2` (June 2024) — Bayesian-optimization search over the joint
  instruction+demo space; a `prompt_model` proposes instructions while a
  `task_model` runs the program. `auto="light"/"medium"/"heavy"` sets the budget.
  Often described as the current state-of-the-art when both instructions and demos
  need tuning together.
- `SIMBA` — mini-batch, SGD-flavored search that reacts to the current
  worst-performing examples each step, proposing either an instruction patch or a
  new demo.
- `InferRules` — extends `BootstrapFewShot` by asking a teacher LM to read the
  bootstrapped demos and distill explicit, human-readable rules, appended to the
  instructions.

**Fine-tune weights:**
- `BootstrapFinetune` — bootstraps traces like `BootstrapFewShot`, then uses them as
  training data to fine-tune the student LM's weights. Requires an LM with a
  fine-tuning API. This is the direct descendant of the paper's
  `BootstrapFinetune` (used in the paper to distill compiled Llama2-13b-chat
  programs down to a 770M-parameter T5-Large).

**Compose optimizers:**
- `BetterTogether` (July 2024) — runs a specified sequence like `"p -> w -> p"`
  (prompt optimize, then weight tune, then prompt optimize again).
- `Ensemble` — not an optimizer over a single program; combines several already-
  compiled programs into one that runs all of them and reduces (default: majority
  vote). Direct descendant of the paper's ensembling stage.

**Specialized:**
- `AvatarOptimizer` — built for agent-style programs; partitions the trainset by
  metric score into positive/negative examples and proposes instruction edits that
  explain the difference.

## Design facts worth knowing when explaining "why" questions

- `.compile()` always returns a new copy; the original student module is left
  untouched, so re-running with different optimizers/budgets never leaks state.
- After a successful compile, the module is flagged `_compiled=True`, which tells
  any *outer* optimizer wrapping it to leave that sub-module alone — this is what
  makes "optimize inner module → embed in a bigger program → optimize the outer
  program" a supported pattern.
- Prompt-only optimizers (BootstrapFewShot family, COPRO, MIPROv2, GEPA, SIMBA, ...)
  work against any LM, including closed-source APIs, because they never touch model
  weights. Only `BootstrapFinetune` (and the weight-tuning leg of `BetterTogether`)
  requires a model that exposes fine-tuning.
- Demo-tuning (few-shot examples) tends to overfit to the trainset's specific
  distribution; instruction-tuning tends to generalize better. A useful default: if
  the eval set is small or skewed, lean toward instruction optimization (COPRO/GEPA)
  over demo optimization.
- Compiling is expensive (GEPA/MIPROv2 runs can cost real money in LM calls);
  inference against a compiled/saved program is cheap. The economics only work if you
  compile once per program version and save+reload the artifact
  (`program.save(path)`) rather than recompiling per request.
- There is no automatic optimizer selection — DSPy doesn't introspect the task and
  pick for you. The `auto=` knobs on MIPROv2/GEPA only set *budget* within that
  optimizer.

## Selection cheat sheet

| Situation | Try |
|---|---|
| Just starting, no idea what helps | `BootstrapFewShot` |
| Demo quality varies across attempts | `BootstrapFewShotWithRandomSearch` |
| Large trainset; different inputs need different demos | `KNNFewShot` |
| Instructions look wrong, demos look fine | `COPRO` or `GEPA` |
| Both instructions and demos look weak, and you have budget | `MIPROv2` or `GEPA` |
| Failure cases share a nameable pattern | `SIMBA` or `InferRules` |
| Prompt-only optimization has plateaued and the model is tunable | `BootstrapFinetune` |
| Want to combine prompt + weight tuning | `BetterTogether` |
| Multiple competent compiled programs to combine | `Ensemble` |
| Agent / tool-use task | `AvatarOptimizer` or `GEPA` |
