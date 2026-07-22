- source_spec: `_bmad-output/implementation-artifacts/spec-refactor-cleanup-densify-2.md`
  summary: `_ensure_schema` em experience_store_sqlite.py hardcoded `PRAGMA user_version = 1` — constante SCHEMA_VERSION removida deixou número mágico sem exposição programática
  evidence: SCHEMA_VERSION era a única referência nomeada ao schema version; sem ela, qualquer lógica de migração futura depende de número mágico enterrado em SQL

- source_spec: `_bmad-output/implementation-artifacts/spec-refactor-cleanup-densify-2.md`
  summary: `_apply_safety_net` extraída sem teste unitário próprio — coberta apenas indiretamente via `_run_with_fail_fast`
  evidence: Função standalone com 3 early-returns e 2 branches de tipo merece cobertura direta; refatoração reduziu acoplamento mas não adicionou harness

- source_spec: `_bmad-output/implementation-artifacts/spec-refactor-cleanup-densify-2.md`
  summary: `load_drift_history` em history.py ficou totalmente órfã após remoção de `append_drift_report` (seu único chamador)
  evidence: grep em toda a codebase confirma zero referências externas; era transitivamente morta antes mas agora é detectable pelo vulture

- source_spec: `_bmad-output/implementation-artifacts/spec-audit-bugs.md`
  summary: `_drain_pending_events` materializa fila inteira em lista em vez de fazer yield incremental
  evidence: Código antigo fazia yield direto no gerador; novo código aloca lista completa antes de iterar, aumentando pico de memória em conexões SSE com filas grandes
