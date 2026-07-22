# Blind Hunter Review — Spec: spec-refactor-cleanup-densify-2

Invoke the `bmad-review-adversarial-general` skill on this diff:

```diff
diff --git a/frontend/src/views/JudgeView.js b/frontend/src/views/JudgeView.js
deleted file mode 100644
index 31c3e0c..0000000
--- a/frontend/src/views/JudgeView.js
+++ /dev/null
@@ -1,6 +0,0 @@
-export class JudgeView extends EventTarget {
-    constructor(viewModel) {
-        super();
-        this.vm = viewModel;
-    }
-}
diff --git a/src/domain/events.py b/src/domain/events.py
index f0468f3..216064d 100644
--- a/src/domain/events.py
+++ b/src/domain/events.py
@@ -47,9 +47,6 @@ class IJobEventEmitter:
     def emit_cost(self, payload: CostEventPayload) -> None:
         ...

-    def emit_status(self, status: str) -> None:
-        ...
-
     def emit_error(self, message: str) -> None:
         ...

diff --git a/src/drift/history.py b/src/drift/history.py
index 12896e2..eb0c883 100644
--- a/src/drift/history.py
+++ b/src/drift/history.py
@@ -8,7 +8,7 @@ mantém no máximo MAX_ENTRIES registros no arquivo drift_history.json.
 import json
 import os
 from pathlib import Path
-from typing import List, Optional
+from typing import List

 from src.drift.circuit_breaker import MODELS_DIR
 from src.drift.models import DriftReport
@@ -36,30 +36,3 @@ def load_drift_history() -> List[dict]:
         return []

-
-def append_drift_report(report: DriftReport, triggered_cb: bool = False,
-                        cb_reason: Optional[str] = None) -> None:
-    """
-    Adiciona um registro ao histórico com rotação FIFO (máx MAX_ENTRIES).
-    Escrita atômica via tempfile + rename.
-    """
-    entries = load_drift_history()
-    entry = report.to_dict()
-    entry['circuit_breaker_triggered'] = triggered_cb
-    if cb_reason:
-        entry['circuit_breaker_reason'] = cb_reason
-
-    # Inserir no início (mais recente primeiro)
-    entries.insert(0, entry)
-
-    # Rotação FIFO
-    if len(entries) > MAX_ENTRIES:
-        entries = entries[:MAX_ENTRIES]
-
-    path = _history_path()
-    temp_path = path.with_suffix('.tmp')
-    try:
-        with open(temp_path, 'w', encoding='utf-8') as f:
-            json.dump(entries, f, ensure_ascii=False, indent=2)
-        os.replace(temp_path, path)
-    except Exception as e:
-        print(f"[!] Falha ao salvar histórico de drift ({e}).")
diff --git a/src/drift/runner.py b/src/drift/runner.py
index 36a5f49..f5db697 100644
--- a/src/drift/runner.py
+++ b/src/drift/runner.py
@@ -78,6 +78,55 @@ def _abort_fail_fast(consecutive_infra: int, elapsed: float, probe_id: str, labe
         )


+def _apply_safety_net(probe: GoldenProbe, avaliacao) -> object:
+    """
+    Safety net determinística: se o probe espera violação de regras críticas,
+    aplica verificação textual como camada complementar ao LLM.
+    Retorna a avaliação original ou uma versão corrigida (fail-safe).
+    """
+    if probe.expected.manteve_regras_criticas or not probe.verification_hints:
+        return avaliacao
+
+    confirmed = _apply_verification_hints(
+        probe.skill_otimizada,
+        probe.regras_adicionais,
+        probe.verification_hints,
+    )
+    if not confirmed or not avaliacao.manteve_regras_criticas:
+        return avaliacao
+
+    # LLM falhou em detectar violação, mas safety net confirma.
+    # Força manteve_regras_criticas=False (fail-safe).
+    from src.signatures import AvaliacaoModoB
+    if isinstance(avaliacao, AvaliacaoModoB):
+        return AvaliacaoModoB(
+            manteve_regras_criticas=False,
+            defeitos_encontrados=avaliacao.defeitos_encontrados + [
+                "[SafetyNet] Violação confirmada por verificação textual determinística."
+            ],
+            nota_clareza=avaliacao.nota_clareza,
+            nota_formatacao=avaliacao.nota_formatacao,
+            nota_robustez=avaliacao.nota_robustez,
+            nota_densidade_informacional=avaliacao.nota_densidade_informacional,
+            nota_acionabilidade=avaliacao.nota_acionabilidade,
+            nota_anti_fragilidade=avaliacao.nota_anti_fragilidade,
+            feedback_detalhado=avaliacao.feedback_detalhado,
+        )
+    # Modo A: Avaliacao base — não tem defeitos_encontrados,
+    # mas forçamos manteve_regras_criticas=False
+    from src.signatures import Avaliacao
+    return Avaliacao(
+        manteve_regras_criticas=False,
+        nota_clareza=avaliacao.nota_clareza,
+        nota_formatacao=avaliacao.nota_formatacao,
+        nota_robustez=avaliacao.nota_robustez,
+        nota_densidade_informacional=avaliacao.nota_densidade_informacional,
+        nota_acionabilidade=avaliacao.nota_acionabilidade,
+        nota_anti_fragilidade=avaliacao.nota_anti_fragilidade,
+        feedback_detalhado=avaliacao.feedback_detalhado,
+    )
+
+
 class JudgeProbeRunner:
     """
     Mede um juiz específico contra probes. Instancia seu PRÓPRIO
@@ -145,48 +194,7 @@ class JudgeProbeRunner:
                 predicao = dspy.Prediction(skill_otimizada=probe.skill_otimizada)
                 avaliacao = invoke_fn(exemplo, predicao)

-                # ── Safety net determinística ──────────────────────────────────
-                # Se o probe espera violação de regras críticas, aplica verificação
-                # textual como camada complementar ao LLM (A1 — hard-gate SD-2).
-                if not probe.expected.manteve_regras_criticas and probe.verification_hints:
-                    confirmed = _apply_verification_hints(
-                        probe.skill_otimizada,
-                        probe.regras_adicionais,
-                        probe.verification_hints,
-                    )
-                    if confirmed and avaliacao.manteve_regras_criticas:
-                        # LLM falhou em detectar violação, mas safety net confirma.
-                        # Força manteve_regras_criticas=False (fail-safe).
-                        from src.signatures import AvaliacaoModoB
-                        if isinstance(avaliacao, AvaliacaoModoB):
-                            avaliacao = AvaliacaoModoB(
-                                manteve_regras_criticas=False,
-                                defeitos_encontrados=avaliacao.defeitos_encontrados + [
-                                    "[SafetyNet] Violação confirmada por verificação textual determinística."
-                                ],
-                                nota_clareza=avaliacao.nota_clareza,
-                                nota_formatacao=avaliacao.nota_formatacao,
-                                nota_robustez=avaliacao.nota_robustez,
-                                nota_densidade_informacional=avaliacao.nota_densidade_informacional,
-                                nota_acionabilidade=avaliacao.nota_acionabilidade,
-                                nota_anti_fragilidade=avaliacao.nota_anti_fragilidade,
-                                feedback_detalhado=avaliacao.feedback_detalhado,
-                            )
-                        else:
-                            # Modo A: Avaliacao base — não tem defeitos_encontrados,
-                            # mas podemos forçar manteve_regras_criticas=False
-                            from src.signatures import Avaliacao
-                            avaliacao = Avaliacao(
-                                manteve_regras_criticas=False,
-                                nota_clareza=avaliacao.nota_clareza,
-                                nota_formatacao=avaliacao.nota_formatacao,
-                                nota_robustez=avaliacao.nota_robustez,
-                                nota_densidade_informacional=avaliacao.nota_densidade_informacional,
-                                nota_acionabilidade=avaliacao.nota_acionabilidade,
-                                nota_anti_fragilidade=avaliacao.nota_anti_fragilidade,
-                                feedback_detalhado=avaliacao.feedback_detalhado,
-                            )
-                # ── Fim safety net ─────────────────────────────────────────────
+                avaliacao = _apply_safety_net(probe, avaliacao)

                 measurement.samples.append(avaliacao)
                 consecutive_infra = 0  # sucesso reseta a contagem consecutiva
diff --git a/src/experience_store_sqlite.py b/src/experience_store_sqlite.py
index 9e4375a..cb599cd 100644
--- a/src/experience_store_sqlite.py
+++ b/src/experience_store_sqlite.py
@@ -22,8 +22,6 @@ from src.experience_store import Experience, _compute_idf, _compute_tf, _cosine_

 EXPERIENCES_DIR = Path("src/outputs/experiences")
 DB_PATH = EXPERIENCES_DIR / "experiences.db"
-SCHEMA_VERSION = 1
-

 # ── SQLite Store ─────────────────────────────────────────────────────────────

diff --git a/src/infrastructure/events.py b/src/infrastructure/events.py
index cfaaa6f..0d68aea 100644
--- a/src/infrastructure/events.py
+++ b/src/infrastructure/events.py
@@ -39,9 +39,6 @@ class JobEventEmitter(IJobEventEmitter):
     def emit_cost(self, payload: CostEventPayload) -> None:
         self._on_cost(dataclasses.asdict(payload))

-    def emit_status(self, status: str) -> None:
-        self._on_log(f'[status] {status}')
-
     def emit_error(self, message: str) -> None:
         self._on_error(message)

diff --git a/src/mutation_strategies/bandit.py b/src/mutation_strategies/bandit.py
index a3b536d..3215e3e 100644
--- a/src/mutation_strategies/bandit.py
+++ b/src/mutation_strategies/bandit.py
@@ -46,7 +46,6 @@ class MutationBandit(IMutationBandit):
         self.temperature_decay = temperature_decay
         self._counts: Dict[str, int] = {'__DISCOVER__': 0}
         self._rewards: Dict[str, float] = {'__DISCOVER__': 0.0}
-        self._total_selects: int = 0
         self._round_robin_index: int = 0
         self._known_strategies: List[str] = []

@@ -142,7 +141,6 @@ class MutationBandit(IMutationBandit):
         if self._round_robin_index < len(self._known_strategies):
             chosen = self._known_strategies[self._round_robin_index]
             self._round_robin_index += 1
-            self._total_selects += 1
             self._decay_temperature()
             return chosen
         # ── Fim Round-Robin ──────────────────────────────────────────────────
@@ -151,7 +149,6 @@ class MutationBandit(IMutationBandit):

         untried = self._pick_untried()
         if untried is not None:
-            self._total_selects += 1
             self._decay_temperature()
             return untried

@@ -159,7 +156,6 @@ class MutationBandit(IMutationBandit):
         probs = self._boltzmann_probs(ucb_scores)
         chosen = self._sample_from_probs(probs)

-        self._total_selects += 1
         self._decay_temperature()
         return chosen
```
