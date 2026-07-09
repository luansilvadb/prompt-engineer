# CONCERNS.md

**Date:** 2026-07-09
**Scope:** Full Repo

## Technical Debt & Issues
- **File System Persistence**: Reliance on local `json`/`jsonl` files (`outputs/` directory) for state and history. This makes concurrent scaling (multiple worker nodes) and data integrity hard without a proper database or distributed locking.
- **Lack of Traditional Testing**: While LLM evaluation is present (`drift_monitor.py`), the lack of a standard test suite (`pytest`) for the deterministic logic (like endpoints and calculations) might lead to preventable regressions.
- **Coupling**: Core logic files are somewhat large and mix concerns (e.g. `drift_monitor.py` contains classes for domain exceptions, metric calculations, and file IO).

## Security
- Potential risk of exposing static API keys or endpoints in logs if LiteLLM logging is verbose (`os.environ['LITELLM_LOG'] = 'DEBUG'`).
- Broad CORS rules (`allow_origins=['*']`) on the FastAPI app.
