# Signatures and Modules

## Signatures

A signature is a declarative spec of a text transformation's input/output
behavior — a tuple of input fields, output fields, and an optional instruction. It
tells DSPy *what* a transformation should do, not *how* to prompt for it. DSPy turns
field names and types into a formatted prompt, and later an optimizer can rewrite the
instruction wording or attach demonstrations without the surrounding code changing.

### Shorthand syntax (stable since the 2023 paper)

```python
qa = dspy.Predict("question -> answer")
qa(question="Where is Guaraní spoken?")
# Prediction(answer="Guaraní is spoken mainly in South America.")
```

Field names carry semantic meaning that DSPy expands into instructions — e.g.
`"english_document -> french_translation"` implies a translation task without any
prose instruction being written by hand. Multiple inputs/outputs are comma-separated:
`"context, question -> answer"`.

### Class-based syntax

**2023 paper version** — explicit fields, no type enforcement:

```python
class GenerateSearchQuery(dspy.Signature):
    """Write a simple search query that will help answer a complex question."""
    context = dspy.InputField(desc="may contain relevant facts")
    question = dspy.InputField()
    query = dspy.OutputField(dtype=dspy.SearchQuery)  # typing was experimental/WIP
```

**Current (2026) version** — Python type hints are first-class and enforced/parsed
by DSPy, not just descriptive:

```python
class Triage(dspy.Signature):
    """Route a support ticket."""
    ticket: str = dspy.InputField()
    urgency: Literal["low", "high"] = dspy.OutputField()
    team: str = dspy.OutputField()
```

Current signature field types go well beyond plain strings: `Literal[...]` for
enums/classification, `list[str]`, `dict`, `Optional[str]`, and even multimodal types
like `dspy.Image` and `dspy.Audio` as **input field types** — meaning DSPy signatures
can describe multimodal tasks (e.g. "chart: dspy.Image -> trend: str,
data_points: list[dict]") natively.

Advanced signature knobs available in both eras: `desc=` on fields for extra guidance,
docstrings as task-level instructions, and (in the current library) full
`InputField`/`OutputField` objects with prefixes.

## Modules

A module *implements* a signature using some prompting/reasoning strategy. Modules
are the DSPy analogue of neural-network layers: instantiate at `__init__`, call like
a function, and they carry learnable parameters (an optional LM override, and a list
of demonstrations used for few-shot prompting or as fine-tuning data).

Swapping modules is a one-line change because they're generic over any signature:

```python
classify = dspy.Predict(Triage)          # direct completion
classify = dspy.ChainOfThought(Triage)   # + step-by-step reasoning
classify = dspy.ReAct(Triage, tools=[search])  # + tools and a reasoning loop
```

### Built-in modules

| Module | What it does | Era |
|---|---|---|
| `Predict` | The base module. Formats a prompt from a signature + demos, calls the LM, parses outputs. Every other module is built from one or more `Predict` calls. | Paper + current |
| `ChainOfThought` | Prepends a `rationale` output field ("Reasoning: Let's think step by step...") before the real outputs, implemented as a signature rewrite wrapping `Predict`. | Paper + current |
| `ProgramOfThought` | Generates and executes code to derive the answer, rather than reasoning purely in natural language (generalizes Chen et al.'s Program-of-Thoughts). | Paper + current |
| `MultiChainComparison` | Samples several reasoning chains (e.g. via `n=` on ChainOfThought) and compares them to synthesize a single, better answer (generalizes Yoran et al.'s reasoning-over-multiple-chains). | Paper + current |
| `ReAct` | Multi-step tool-use agent: interleaves Thought / Action / Observation steps (Yao et al.'s ReAct pattern), taking a `tools=[...]` list. | Paper + current (current version accepts plain Python functions as tools, and there's now a `ReActV2`) |
| `Retrieve` | Wraps a retrieval backend (originally ColBERTv2, Pyserini, Pinecone). | Paper (now typically expressed via `dspy.Tool`/retriever objects rather than a dedicated `Retrieve` class in idiomatic current code, though the concept persists) |
| `Refine` | Iteratively refines an output against a reward/quality signal. | Current |
| `BestOfN` | Samples N completions and selects the best by a reward function — a lighter-weight alternative to full refinement. | Current |
| `CodeAct` | Agent loop that reasons and acts by writing and executing code (related to, but distinct from, `ProgramOfThought`). | Current |
| `Parallel` | Runs sub-modules concurrently and aggregates results. | Current |
| `RLM` | "Recursive Language Models" — lets a program explore very large contexts by having the LM write and run code over them rather than reading everything in-context. Newest addition (Dec 2025 research). | Current |

### Composing custom modules

Same pattern in both eras: declare sub-modules in `__init__`, wire them together with
arbitrary Python control flow in `forward()`.

```python
class RAG(dspy.Module):
    def __init__(self, num_passages=3):
        self.retrieve = dspy.Retrieve(k=num_passages)
        self.generate_answer = dspy.ChainOfThought("context, question -> answer")

    def forward(self, question):
        context = self.retrieve(question).passages
        return self.generate_answer(context=context, question=question)
```

Because `forward()` is plain Python, arbitrary logic is allowed — `if` statements,
loops, exceptions, calling sub-modules multiple times (as in multi-hop retrieval,
where `generate_query`/`retrieve` run in a loop before a final `generate_answer`
call).

### Tools and multimodality (current-era specifics)

- Tools passed to `ReAct` (or used directly via `dspy.Tool`) are plain Python
  functions with docstrings and type hints — DSPy infers the tool schema from the
  function signature, no special wrapper class required.
- MCP (Model Context Protocol) servers can supply tools directly into DSPy agent
  loops (`tools, react, and mcp` in the docs) — a capability that didn't exist at
  paper time.
- Multimodal fields (`dspy.Image`, `dspy.Audio`) let a signature declare, e.g., an
  image input and structured outputs describing it, with the same `Predict`/module
  machinery as text-only signatures.
