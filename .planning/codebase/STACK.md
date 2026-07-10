# STACK.md

**Date:** 2026-07-09
**Scope:** Full Repo

## Technologies

- **Language:** Python
- **Web Framework:** FastAPI
- **LLM Orchestration:** DSPy
- **LLM Gateway:** LiteLLM
- **Environment config:** python-dotenv

## Dependencies
- `fastapi`
- `dspy-ai`
- `litellm`
- `python-dotenv`
- `sentence-transformers`
- `torch`

## Runtimes
- standard CPython

## Key Configurations
- `config.py`: Uses `os.environ` and `.env` variables to configure LiteLLM/DSPy endpoints, API keys, and MCTS parameters (`MCTS_GAMMA`, `MCTS_C_PARAM`, `DRIFT_SPEARMAN_FLOOR`, etc.).
