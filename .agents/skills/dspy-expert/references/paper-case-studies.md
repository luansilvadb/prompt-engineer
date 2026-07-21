# The Original Paper (arXiv:2310.03714) — Deep Detail

Use this file when the user is working directly from the uploaded/discussed paper
(Khattab, Singhvi, Maheshwari, et al., "DSPy: Compiling Declarative Language Model
Calls Into Self-Improving Pipelines," Stanford/UC Berkeley/CMU, Oct 2023) and wants
historically accurate detail — pseudocode, exact numbers, or the original framing —
rather than current-library specifics.

## The three hypotheses the paper tests

- **H1**: DSPy can replace hand-crafted prompt strings with concise, well-defined
  modules without losing quality or expressive power.
- **H2**: Parameterizing modules and treating prompting as an optimization problem
  helps DSPy adapt better across different LMs, potentially outperforming
  expert-written prompts.
- **H3**: The resulting modularity makes it possible to more thoroughly explore
  complex pipelines suited to nuanced metrics.

## Case study 1: GSM8K (math word problems)

Three programs, each 2–4 lines of DSPy:

- `vanilla = dspy.Predict("question -> answer")`
- `CoT = dspy.ChainOfThought("question -> answer")`
- `reflection` (`ThoughtReflection`): samples 5 reasoning chains via
  `dspy.ChainOfThought("question -> answer", n=5)`, then compares them with
  `dspy.MultiChainComparison("question -> answer", M=5)`.

Compilers used: `LabeledFewShot(k=8)` (`fewshot`), `BootstrapFewShotWithRandomSearch`
(`bootstrap`), nesting a second bootstrap pass on top of the first (`bootstrap×2`),
and majority-vote ensembling of the top-7 candidates from a bootstrap run.

**Headline result**: across every program, compiling with `bootstrap` instead of
hand-written prompts raised GPT-3.5 and llama2-13b-chat from **4–20% accuracy to
49–88% accuracy** on GSM8K. The `reflection` program with ensembling reached 86.7%
(GPT-3.5) / 49.0–46.9% (llama2-13b-chat dev/test). Bootstrapped CoT matched or beat
prompts that used the dataset's own human-written reasoning chains.

## Case study 2: HotPotQA (open-domain multi-hop QA)

Programs: `vanilla` (reused from GSM8K), `CoT RAG` (single-hop retrieval + CoT
answer generation), `ReAct` (via `dspy.ReAct("question -> answer",
tools=[dspy.Retrieve(k=1)], max_iters=5)`), and a custom `BasicMultiHop` module that
alternates `generate_query` and `retrieve` calls across 2 hops before a final
`generate_answer` call (modeled after Baleen/IRRR/IRCoT).

**Headline result**: the multihop program with `bootstrap` compilation performed
best overall; ensembling pushed GPT-3.5 dev answer-EM to 54.7%. A distilled
`multihop_t5` — a 770M-parameter T5-Large fine-tuned via `BootstrapFinetune` using a
compiled llama2-13b-chat ensemble as teacher, on only 200 labeled + 800 unlabeled
questions — scored 39.3% answer EM / 46.0% passage accuracy, demonstrating that DSPy
compilation can transfer quality down to a much smaller, cheaper open model.

## Historical pseudocode worth knowing (Appendix D/E of the paper)

These are simplified/illustrative, not literal current source:

**`Predict`** (the base module): stores a signature, an optional LM override
(defaults to `None`, meaning "use the default LM"), and a list of demonstrations
(initially empty). On `forward()`, it builds a prompt from the signature + demos,
calls the LM, parses completions into a `Prediction`, and — when running in "compile
mode" — records an input/output trace for the teleprompter to use later.

**`ChainOfThought`**: rewrites the wrapped signature from `*inputs -> *outputs` to
`*inputs -> rationale, *outputs` by prepending an output field with the prefix
"Reasoning: Let's think step by step," then delegates to a `Predict` over the
rewritten signature. This is why literally any signature can be wrapped in
`ChainOfThought` with zero rewriting elsewhere.

**`BootstrapFewShot`** (simplified): for each training example, runs a teacher
program (defaults to the zero-shot version of the student) with compile mode on,
captures the trace of every internal `Predict` call, and — if the metric accepts the
final prediction — adds each captured (inputs, outputs) pair as a demonstration to
the corresponding predictor. Stops once "enough" bootstrapped demos are found.

**`BootstrapFewShotWithRandomSearch`**: runs the above with `trials` different
shuffles/seeds of the trainset and a randomized bootstrap size, evaluates every
resulting candidate program against a validation set, and returns the highest-scoring
candidate.

## Comparison with LangChain / LlamaIndex (paper Appendix B)

The paper's core distinction: LangChain and LlamaIndex focus on **pre-packaged,
reusable chains and agents plus tool integrations** for application developers — but
internally they still rely on long, hand-written prompt template strings. DSPy's
target is one level lower: the prompt-engineering problem itself, via signatures,
modules, and teleprompters as composable operators, with prompts *generated and
optimized* rather than authored.

The paper backs this with an informal audit (late Sept 2023): the LangChain codebase
contained 50 strings over 1000 characters (mostly prompts) plus dozens of files
dedicated to prompt templating, versus zero hand-written prompt demonstrations
anywhere in DSPy at the time. Appendix C of the paper reproduces several
representative large hand-written prompts from LangChain/LlamaIndex/research papers
(a PAL few-shot prompt at ~3957 characters, a ReAct prompt at ~3889 characters, a
"QA with sources" prompt at ~6197 characters, etc.) as points of comparison against
DSPy's few-line, auto-compiled equivalents.

## Framing to reuse when explaining the paper's motivation

The paper draws an explicit analogy to the deep learning community's own history:
just as neural network research moved from hand-tuned weights to composable general
layers optimized by learned algorithms (citing the Torch/Theano/PyTorch lineage),
DSPy aims to move LM pipeline development from hand-tuned prompt strings to
composable general modules optimized by a compiler. "Teleprompter" is named for
automating the *prompting itself*, at a distance, without manual intervention — the
same spirit as the paper's overall thesis.
