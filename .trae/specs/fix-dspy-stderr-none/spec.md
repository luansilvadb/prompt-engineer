# Corrigir AttributeError no dspy com sys.stderr None

## Why
O build PyInstaller com `console=False` torna `sys.stderr = None`. A biblioteca `dspy` (em `dspy/utils/logging_utils.py:26`) chama `sys.stderr.flush()` sem verificar se `sys.stderr` não é `None`, causando `AttributeError: 'NoneType' object has no attribute 'flush'` durante a inicialização do uvicorn.

## What Changes
- Adicionar guarda no início de `scripts/desktop.py`: se `sys.stderr is None`, redirecioná-lo para `os.devnull`
- Isso protege todo o código downstream (dspy, uvicorn, logging) que assume `sys.stderr` válido

## Impact
- Affected specs: Nenhum
- Affected code: `scripts/desktop.py`

## ADDED Requirements
### Requirement: sys.stderr Resiliente
O sistema DEVE garantir que `sys.stderr` seja sempre um stream válido (nunca `None`) antes que qualquer biblioteca externa tente usá-lo.

#### Scenario: Build PyInstaller sem console
- **WHEN** `desktop.py` é executado no ambiente congelado com `console=False`
- **THEN** `sys.stderr` é redirecionado para `os.devnull`
- **AND** chamadas a `sys.stderr.flush()` em dspy/uvicorn/logging não causam `AttributeError`

#### Scenario: Execução normal
- **WHEN** `desktop.py` é executado via `python scripts/desktop.py`
- **THEN** `sys.stderr` mantém seu valor original (terminal)
- **AND** logs de console funcionam normalmente
