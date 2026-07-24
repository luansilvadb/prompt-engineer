# Correção de NameError: logger não definido em services.py

## Why
O arquivo `src/services.py` contém chamadas diretas a `logger.info()` e `logger.error()` (linhas 146, 150, 158-161, 171-174) sem que o objeto `logger` tenha sido importado ou instanciado. Isso causa `NameError: name 'logger' is not defined` em runtime, interrompendo a execução de qualquer job de otimização no momento em que tenta registrar conclusão, cancelamento ou falha. A spec anterior `fix-optimizer-log-issues` introduziu essas chamadas na Task 4 mas não incluiu a definição do logger.

## What Changes
- Adicionar `import logging` e `logger = logging.getLogger(__name__)` no topo de `src/services.py`

## Impact
- Affected specs: `fix-optimizer-log-issues` (corrige regressão introduzida pela Task 4 daquela spec)
- Affected code: `src/services.py`

## MODIFIED Requirements

### Requirement: Logger deve estar definido antes do uso
O sistema DEVE garantir que o objeto `logger` esteja importado e instanciado no módulo `src/services.py` antes de qualquer uso.

#### Scenario: Job concluído com sucesso
- **WHEN** uma otimização termina todas as iterações com sucesso
- **THEN** o sistema deve registrar `logger.info(...)` com job_id, duração, e métricas
- **AND** NÃO deve lançar `NameError: name 'logger' is not defined`

#### Scenario: Job que falha
- **WHEN** uma otimização encontra um erro não recuperável
- **THEN** o sistema deve registrar `logger.error(...)` com job_id, duração, e detalhes da falha
- **AND** NÃO deve lançar `NameError: name 'logger' is not defined`

#### Scenario: Job cancelado
- **WHEN** um job é cancelado pelo usuário
- **THEN** o sistema deve registrar `logger.info(...)` com job_id e duração
- **AND** NÃO deve lançar `NameError: name 'logger' is not defined`
