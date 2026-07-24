# Correção de Anomalias do Log do Optimizer

## Why
O arquivo de log `optimizer_2026-07-23.log` (~9h de operação) revela múltiplas anomalias críticas que comprometem a estabilidade e eficiência do aplicativo: bugs de coroutine não aguardada causando `AttributeError`, SSE streams órfãos, golden sets com JSON malformado, e latência excessiva na inicialização de jobs. Nenhum job de otimização apresentou evidência de conclusão bem-sucedida no período analisado.

## What Changes
- Corrigir bug de `await` faltante em `get_job` nos endpoints `delete_job_endpoint` e `stop_optimization` (**BREAKING**: muda comportamento de runtime, corrige crash)
- Adicionar limpeza proativa de SSE streams de sessões anteriores ao iniciar nova conexão
- Adicionar validação e tratamento robusto de JSON malformado no carregamento de golden sets
- Implementar timeout e retry na inicialização de jobs para reduzir latência
- Adicionar logging de conclusão/falha de jobs para rastreabilidade
- Implementar heartbeat periódico em jobs long-running para evitar falsos órfãos

## Impact
- Affected specs: N/A (novo)
- Affected code: `src/routers/jobs.py`, `src/drift/golden.py`, `src/infrastructure/exception_handlers.py`

## ADDED Requirements

### Requirement: Correção de Await em Endpoints
O sistema DEVE garantir que toda chamada a funções assíncronas utilize `await` adequadamente, prevenindo `AttributeError` em runtime.

#### Scenario: DELETE job com ID inexistente
- **WHEN** uma requisição DELETE é feita para `/api/jobs/{job_id}` onde `job_id` não existe
- **THEN** o endpoint deve retornar HTTP 404 com mensagem "Job not found"
- **AND** NÃO deve lançar `AttributeError: 'coroutine' object has no attribute 'is_deleted'`

#### Scenario: POST stop com ID inexistente
- **WHEN** uma requisição POST é feita para `/api/stop/{job_id}` onde `job_id` não existe
- **THEN** o endpoint deve retornar HTTP 404 com mensagem "Job not found"
- **AND** NÃO deve lançar `AttributeError: 'coroutine' object has no attribute 'status'`

### Requirement: Limpeza de SSE Streams Órfãos
O sistema DEVE limpar conexões SSE de sessões anteriores ao iniciar uma nova conexão para o mesmo job, prevenindo CancelledError e acúmulo de streams.

#### Scenario: Reconexão SSE para job existente
- **WHEN** um cliente inicia um novo SSE stream para um job que já possui um stream ativo de sessão anterior
- **THEN** o sistema deve encerrar o stream anterior antes de iniciar o novo
- **AND** não deve emitir CancelledError que polui o log

### Requirement: Validação de Golden Set
O sistema DEVE validar JSON de golden sets antes de carregá-los e fornecer mensagens de erro acionáveis.

#### Scenario: Golden set com JSON malformado
- **WHEN** um arquivo de golden set contém JSON sintaticamente inválido
- **THEN** o sistema deve registrar um WARNING claro com o caminho do arquivo e o erro exato
- **AND** deve incluir uma dica de correção (ex: "Verifique se o arquivo usa aspas duplas")
- **AND** deve operar em fail-open com métricas de drift desabilitadas

### Requirement: Logging de Conclusão de Job
O sistema DEVE registrar explicitamente quando um job de otimização é concluído (com sucesso ou falha).

#### Scenario: Job concluído com sucesso
- **WHEN** uma otimização termina todas as iterações com sucesso
- **THEN** o sistema deve registrar INFO com job_id, duração total, e métricas finais

#### Scenario: Job que falha
- **WHEN** uma otimização encontra um erro não recuperável
- **THEN** o sistema deve registrar ERROR com job_id, duração, e detalhes da falha

### Requirement: Heartbeat de Jobs Long-Running
O sistema DEVE emitir eventos de heartbeat durante jobs de longa duração para prevenir falsa detecção de orfandade.

#### Scenario: Job sem eventos por > 60s durante processamento legítimo
- **WHEN** um job está ativamente processando mas não emite eventos por mais de 60 segundos
- **THEN** o sistema deve emitir um evento de heartbeat automático
- **AND** o job não deve ser marcado como órfão enquanto o heartbeat estiver ativo

## MODIFIED Requirements

### Requirement: Tratamento de Exceções em Endpoints de Job
O sistema DEVE capturar e tratar exceções inesperadas nos endpoints `delete_job_endpoint` e `stop_optimization`, convertendo-as em respostas HTTP apropriadas em vez de crashes não tratados.

#### Scenario: Erro interno ao deletar job
- **WHEN** ocorre qualquer exceção não prevista durante a deleção de um job
- **THEN** o sistema deve retornar HTTP 500 com mensagem genérica
- **AND** deve registrar o stack trace completo no log para debugging
