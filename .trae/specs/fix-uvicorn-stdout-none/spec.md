# Corrigir AttributeError no uvicorn com sys.stdout None

## Why
O `ColourizedFormatter.__init__` do uvicorn (`uvicorn/logging.py:42`) chama `sys.stdout.isatty()`. Com `console=False` no PyInstaller, `sys.stdout` também é `None` (não apenas `sys.stderr`). A guarda existente em `desktop.py` só trata `sys.stderr`.

## What Changes
- Estender a guarda em `scripts/desktop.py` para também tratar `sys.stdout is None`

## Impact
- Affected specs: fix-dspy-stderr-none
- Affected code: `scripts/desktop.py`

## MODIFIED Requirements
### Requirement: sys.std* Resiliente
O sistema DEVE garantir que `sys.stdout` e `sys.stderr` sejam sempre streams válidos (nunca `None`).

#### Scenario: Build PyInstaller sem console
- **WHEN** `desktop.py` é executado no ambiente congelado com `console=False`
- **THEN** `sys.stdout` e `sys.stderr` são redirecionados para `os.devnull`
- **AND** `sys.stdout.isatty()` e `sys.stderr.isatty()` não causam `AttributeError`
