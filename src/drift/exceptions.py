"""
Drift Monitor — exceções de domínio.

Extrído de ``src/drift_monitor.py`` (L44-50) no plano 01-01 da fase
01-architectural-cleanup-densification. Comportamento idêntico — apenas
relocação para o novo namespace package ``src/drift/``.

Single responsibility: domínio de erro de medição de drift. Nenhum outro
símbolo deve morar neste arquivo.
"""

from typing import Optional


class DriftMeasurementError(Exception):
    """Falha na medição de drift (LLM indisponível, JSON ilegível, etc.)."""

    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
