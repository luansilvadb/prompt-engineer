# Corrigir TypeError no Loguru com sys.stderr None no Build Desktop

## Why
O executável PyInstaller falha em runtime com `TypeError: Cannot log to objects of type 'NoneType'` porque o `.spec` usa `console=False`, o que torna `sys.stderr` `None` no ambiente congelado. A função `setup_logging()` em `logging_config.py` tenta `logger.add(sys.stderr, ...)` sem verificar se `sys.stderr` é válido.

## What Changes
- Adicionar validação de `sys.stderr` antes de registrá-lo como sink no loguru
- Fallback: pular o handler de console ou usar `sys.stdout` quando `sys.stderr` for `None`
- Adicionar tratamento de erro claro com mensagem informativa

## Impact
- Affected specs: Nenhum
- Affected code: `src/infrastructure/logging_config.py`

## MODIFIED Requirements
### Requirement: Logging Setup Resiliente
O sistema DEVE inicializar o logging sem falhar quando `sys.stderr` é `None` (ambiente PyInstaller console=False).

#### Scenario: Build desktop sem console
- **WHEN** `setup_logging()` é chamado no executável PyInstaller com `console=False`
- **THEN** o handler de console é pulado com um aviso
- **AND** o handler de arquivo rotativo é configurado normalmente
- **AND** nenhum `TypeError` é lançado

#### Scenario: Execução normal com console
- **WHEN** `setup_logging()` é chamado via `python main.py` ou `python scripts/desktop.py`
- **THEN** ambos os handlers (console stderr + arquivo rotativo) são configurados normalmente
