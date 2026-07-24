# Tasks

- [x] Task 1: Corrigir bug de `await` faltante em `get_job` nos endpoints `delete_job_endpoint` e `stop_optimization`
  - [x] SubTask 1.1: Localizar a definição da função `get_job` e confirmar que é assíncrona (async def)
  - [x] SubTask 1.2: Adicionar `await` na chamada `get_job` dentro de `delete_job_endpoint` (linha ~141)
  - [x] SubTask 1.3: Adicionar `await` na chamada `get_job` dentro de `stop_optimization` (linha ~122)
  - [x] SubTask 1.4: Adicionar tratamento try/except para capturar exceções e retornar HTTP 404/500 apropriados

- [x] Task 2: Implementar limpeza de SSE streams órfãos ao iniciar nova conexão
  - [x] SubTask 2.1: Identificar o dicionário/registro de streams SSE ativos no módulo jobs
  - [x] SubTask 2.2: Adicionar lógica em `stream_progress` que encerra o stream anterior do mesmo job_id antes de iniciar um novo
  - [x] SubTask 2.3: Substituir CancelledError genérico por log DEBUG (não INFO) quando o cancelamento é intencional

- [x] Task 3: Adicionar validação de JSON no carregamento de golden sets
  - [x] SubTask 3.1: Localizar a função `_load` em `src/drift/golden.py`
  - [x] SubTask 3.2: Adicionar pré-validação com `json.loads` antes do parse principal, capturando `json.JSONDecodeError`
  - [x] SubTask 3.3: Melhorar a mensagem de erro para incluir o caminho do arquivo e dica de correção

- [x] Task 4: Adicionar logging de conclusão/falha de jobs
  - [x] SubTask 4.1: Localizar o ponto de término do processamento de job (onde o status muda para concluído/falha)
  - [x] SubTask 4.2: Adicionar log INFO com job_id, duração, e métricas ao concluir com sucesso
  - [x] SubTask 4.3: Adicionar log ERROR com job_id, duração, e stack trace ao falhar

- [x] Task 5: Implementar heartbeat para jobs long-running
  - [x] SubTask 5.1: Identificar o loop principal de processamento do job
  - [x] SubTask 5.2: Adicionar emissão de evento de heartbeat a cada 30-45 segundos durante processamento
  - [x] SubTask 5.3: Garantir que o mecanismo de detecção de orfandade (`_should_terminate_sse`) respeite heartbeats recentes

# Task Dependencies
- Task 2 depende de Task 1 (mesmo arquivo, mudanças relacionadas)
- Tasks 3, 4, 5 são independentes entre si e podem ser executadas em paralelo
