# Tasks

- [x] Task 1: Adicionar validação de `sys.stderr` e fallback em `setup_logging()`
  - Verificar se `sys.stderr` não é `None` antes de `logger.add(sys.stderr, ...)`
  - Se for `None`, emitir aviso via `warnings.warn()` e pular o handler de console
  - Garantir que o handler de arquivo rotativo seja sempre configurado
