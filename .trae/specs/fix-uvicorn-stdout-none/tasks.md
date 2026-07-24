# Tasks

- [x] Task 1: Adicionar guarda de `sys.stdout` junto à guarda existente de `sys.stderr`
  - Após `if sys.stderr is None:`, adicionar `if sys.stdout is None: sys.stdout = open(os.devnull, 'w')`
