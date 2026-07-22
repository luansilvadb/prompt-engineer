"""Métricas Prometheus para observabilidade do MCTS.

Expõe contadores e histogramas para monitoramento em produção.
Endpoint /metrics no FastAPI (src/api.py).
"""

from prometheus_client import REGISTRY, Counter, Histogram, generate_latest

# ── Contadores ───────────────────────────────────────────────────────────────

mcts_iterations_total = Counter(
    "skill_optimizer_mcts_iterations_total",
    "Total de iterações MCTS executadas",
    ["job_id"],
)

mcts_simulations_total = Counter(
    "skill_optimizer_mcts_simulations_total",
    "Total de simulações (avaliações LLM) executadas",
    ["job_id"],
)

mcts_cache_hits_total = Counter(
    "skill_optimizer_mcts_cache_hits_total",
    "Cache hits (Transposition Table + simulation cache)",
    ["job_id", "cache_type"],
)

mcts_pruned_nodes_total = Counter(
    "skill_optimizer_mcts_pruned_nodes_total",
    "Nós podados antes da simulação",
    ["job_id", "prune_reason"],
)

llm_calls_total = Counter(
    "skill_optimizer_llm_calls_total",
    "Total de chamadas à API LLM",
    ["job_id", "phase"],
)

optimization_duration_seconds = Histogram(
    "skill_optimizer_optimization_duration_seconds",
    "Duração total da otimização",
    ["job_id"],
    buckets=(30, 60, 120, 300, 600, 900, 1800, 3600),
)

jobs_total = Counter(
    "skill_optimizer_jobs_total",
    "Total de jobs processados",
    ["status"],
)


def get_metrics() -> bytes:
    """Retorna métricas no formato Prometheus text exposition."""
    return generate_latest(REGISTRY)
