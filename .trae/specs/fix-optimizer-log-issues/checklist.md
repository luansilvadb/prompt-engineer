# Checklist

- [x] `delete_job_endpoint` usa `await get_job(...)` corretamente e não lança `AttributeError` para IDs inexistentes
- [x] `stop_optimization` usa `await get_job(...)` corretamente e não lança `AttributeError` para IDs inexistentes
- [x] Ambos os endpoints capturam exceções inesperadas e retornam HTTP 500 com log apropriado
- [x] SSE streams antigos são encerrados antes de iniciar novo stream para o mesmo job_id
- [x] CancelledError de cancelamento intencional usa nível DEBUG em vez de INFO
- [x] Golden set com JSON inválido exibe WARNING com caminho do arquivo e dica de correção
- [x] Golden set com JSON válido continua carregando normalmente (sem regressão)
- [x] Jobs concluídos com sucesso registram INFO com job_id, duração e métricas finais
- [x] Jobs que falham registram ERROR com job_id, duração e stack trace
- [x] Heartbeats são emitidos a cada 30-45s durante processamento de jobs long-running
- [x] Mecanismo de detecção de orfandade (`_should_terminate_sse`) respeita heartbeats recentes e não marca jobs ativos como órfãos
