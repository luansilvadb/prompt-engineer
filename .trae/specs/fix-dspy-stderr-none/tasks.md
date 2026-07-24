# Tasks

- [x] Task 1: Adicionar guarda de `sys.stderr` no topo de `desktop.py`
  - Após `import sys`, verificar se `sys.stderr is None`
  - Se `None`, abrir `os.devnull` em modo write e atribuir a `sys.stderr`
  - Garantir que o guarda execute antes de qualquer outro import que possa disparar logging
