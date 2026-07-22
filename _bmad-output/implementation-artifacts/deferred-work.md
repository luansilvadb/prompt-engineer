- source_spec: `D:\good\_bmad-output\implementation-artifacts\spec-refactor-cleanup-densify-3.md`
  summary: Redução de complexidade ciclomática em main.py (_run_watch CC=17) e teleprompter.py (_run_teleprompt CC=16, _evaluate_drift_gate CC=15)
  evidence: Complexidade elevada em funções de runtime exige testes mais extensivos; separado do cleanup mecânico para isolar riscos e facilitar revisão incremental.
- source_spec: `D:\good\_bmad-output\implementation-artifacts\spec-refactor-cleanup-densify-3.md`
  summary: Verificar se `prometheus_client` ainda é usado após remoção de metrics.py — se não, remover de requirements.txt
  evidence: Módulo metrics.py foi removido e nenhum outro arquivo importa prometheus_client; dependência é peso morto.
- source_spec: `D:\good\_bmad-output\implementation-artifacts\spec-refactor-cleanup-densify-3.md`
  summary: Tornar imutáveis as estruturas de dados globais _UNICODE_REPLACEMENTS (dict) e STYLE_BUZZWORDS (list)
  evidence: Mutable module-level state pode ser corrompido acidentalmente por qualquer código que importe essas estruturas.
- source_spec: `D:\good\_bmad-output\implementation-artifacts\spec-refactor-cleanup-densify-3.md`
  summary: Adicionar type guards em _sanitize_unicode_for_api e compute_lexical_density para entradas não-string
  evidence: Funções não validam tipo de entrada; chamadas com None ou tipos errados causam AttributeError em runtime.
- source_spec: `D:\good\_bmad-output\implementation-artifacts\spec-refactor-cleanup-densify-3.md`
  summary: Adicionar warning log para caracteres Unicode não mapeados substituídos silenciosamente por '?' no sanitizer
  evidence: Caracteres como ñ, ü, emoji não têm entrada em _UNICODE_REPLACEMENTS e são substituídos sem aviso.
