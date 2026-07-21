"""
Experimentos de Variância — Pipeline MCTS

Três experimentos independentes para isolar a fonte da inconsistência
entre execuções do Optimizer.optimize().

Uso:
    pytest tests/experiments/test_variance.py -v -s
"""

import statistics
import json
from unittest.mock import MagicMock

from src.domain.config import MCTSConfig
from src.domain.mcts import MCTSNode
from tests.conftest import DeterministicJudge

# ── Helpers ──────────────────────────────────────────────────────────────────

SKILL_BASE = (
    "Você é um assistente de IA. Siga estas regras:\n"
    "1. Sempre responda em português.\n"
    "2. Seja conciso e direto.\n"
    "3. Use formatação markdown quando apropriado.\n"
    "4. Nunca invente informações."
)

FIXED_SKILL_FOR_JUDGE = (
    "## Raciocínio\nPremissas: O usuário precisa de clareza.\n"
    "Deduções: Estrutura melhora compreensão.\n"
    "Conclusão: Usar formato estruturado.\n\n"
    "## Regras\n1. Responda sempre em tópicos.\n"
    "2. Use exemplos concretos.\n\n"
    "## Conclusão\nAplique o formato acima em todas as respostas."
)


def _make_config(max_iterations: int = 5) -> MCTSConfig:
    """Cria uma configuração MCTS enxuta para experimentos rápidos."""
    return MCTSConfig(
        max_iterations=max_iterations,
        c_param=1.41,
        gamma=0.95,
        progressive_alpha=0.5,
        progressive_c=2.0,
        value_threshold=0.2,
        value_lr=0.1,
        bandit_c_param=1.41,
        bandit_temperature=2.0,
        bandit_temperature_decay=0.95,
        semantic_sim_threshold=0.85,
        lexical_density_min=0.35,
        verbosity_penalty_factor=0.85,
        buzzword_threshold=3,
        cognitivo_prior_count=1,
        cognitivo_prior_mean_delta=0.05,
        density_threshold=1.0,
        density_multiplier_min=0.5,
        density_multiplier_max=1.5,
        density_structured_bonus=0.2,
        reward_floor=0.30,
    )


def _run_single_optimize(optimizer_factory, skill_original: str, n_iterations: int,
                         avaliador_modo_b=None, agent_mock=None, agent_cognitivo_mock=None):
    """Roda optimize() uma vez com mocks configuráveis e retorna métricas."""
    opt = optimizer_factory(
        skill_original=skill_original,
        config=_make_config(max_iterations=n_iterations),
        avaliador_modo_b=avaliador_modo_b,
        agent=agent_mock,
        agent_cognitivo=agent_cognitivo_mock,
    )

    root = MCTSNode(skill_original, critica='Rascunho Inicial')
    opt.notify_node(root)
    reward, feedback = opt.simulation(root.instruction)
    root.feedback = feedback
    root.last_reward = reward
    opt.backpropagation(root, reward)

    for i in range(n_iterations):
        should_break, _ = opt._run_mcts_iteration(root)
        if should_break:
            break

    best_node = opt._select_and_log_best_node(root)
    first_3_strategies = [
        entry['strategy_key'] for entry in opt.get_expansion_order()[:3]
    ]

    return {
        'best_reward': best_node.last_reward,
        'best_score': best_node.q_value / max(1, best_node.visits),
        'best_depth': best_node.depth,
        'best_strategy': best_node.mutation_strategy,
        'first_3_strategies': first_3_strategies,
        'expansion_order': opt.get_expansion_order(),
        'level_one_nodes': opt.get_level_one_nodes(root),
        'total_expansions': len(opt.get_expansion_order()),
    }


# ── Experimento A — Variância End-to-End (Baseline) ──────────────────────────

def test_experiment_a_end_to_end_variance(mock_optimizer_factory,
                                          mock_heavy_evaluators):
    """Experimento A: 10 execuções idênticas — mede variância total do pipeline.

    Se este desvio for alto (> 0.10), há instabilidade que precisa ser
    diagnosticada pelos Experimentos B e C.
    """
    N = 10
    ITER = 5
    results = []

    # Configurar agent mock para gerar skills variadas (simula mutação real)
    def _make_agent_mock(strategy_label: str):
        agent = MagicMock()
        agent.nova_instrucao = (
            f"## Raciocínio\nPremissas: feedback analysis.\n"
            f"Deduções: structural improvement via {strategy_label}.\n"
            f"Conclusão: apply format.\n\n"
            f"## Regras\n1. Estratégia: {strategy_label}\n"
            f"2. Mantenha clareza.\n\n"
            f"## Conclusão\nOutput estruturado."
        )
        agent.critica = f"Crítica simulada ({strategy_label})"
        return MagicMock(return_value=agent)

    for run_i in range(N):
        agent_mock = _make_agent_mock(f"run{run_i}")
        result = _run_single_optimize(
            mock_optimizer_factory,
            SKILL_BASE,
            ITER,
            avaliador_modo_b=mock_heavy_evaluators['AvaliadorModoB'],
            agent_mock=agent_mock,
            agent_cognitivo_mock=agent_mock,
        )
        result['run'] = run_i
        results.append(result)

    rewards = [r['best_reward'] for r in results]
    scores = [r['best_score'] for r in results]

    print("\n=== Experimento A: Variance End-to-End ===")
    print(f"  N={N}, iterations={ITER}")
    print(f"  best_reward: mean={statistics.mean(rewards):.3f}, "
          f"stdev={statistics.stdev(rewards):.3f}, "
          f"min-max=[{min(rewards):.3f}, {max(rewards):.3f}]")
    print(f"  best_score:  mean={statistics.mean(scores):.3f}, "
          f"stdev={statistics.stdev(scores):.3f}")
    print("  first_3_strategies por run:")
    for r in results:
        print(f"    run {r['run']}: {r['first_3_strategies']}")

    # Salvar resultados para análise
    with open('tests/experiments/results_exp_a.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Asserts informativos (não bloqueiam — o objetivo é medir, não passar/falhar)
    assert len(results) == N


# ── Experimento B — Isolar Ruído do Juiz LLM ─────────────────────────────────

def test_experiment_b_judge_noise():
    """Experimento B: 10 avaliações da mesma skill fixa — isola ruído do juiz.

    Se o desvio aqui for alto (> 0.08), a Causa 2 (juiz ruidoso) está
    confirmada como fonte principal de variância.
    """
    from src.signatures import funcao_de_recompensa

    N = 10
    results = []

    # Usamos o juiz determinístico como proxy do ruído real.
    # Em produção, trocar para o avaliador_modo_b real.
    judge = DeterministicJudge()
    # Força o juiz a retornar um reward com pequena variância controlada
    # para simular o comportamento de um LLM real.
    judge.set_reward('default', 0.75)

    for i in range(N):
        reward, feedback = funcao_de_recompensa(
            avaliador_modo_b=judge,
            skill_original=SKILL_BASE,
            skill_otimizada=FIXED_SKILL_FOR_JUDGE,
            regras_adicionais="",
        )
        results.append({'run': i, 'reward': reward, 'feedback': feedback})

    rewards = [r['reward'] for r in results]

    print("\n=== Experiment B: Judge Noise ===")
    print(f"  N={N}, fixed skill")
    print(f"  reward: mean={statistics.mean(rewards):.3f}, "
          f"stdev={statistics.stdev(rewards):.3f}, "
          f"min-max=[{min(rewards):.3f}, {max(rewards):.3f}]")
    print(f"  call_log: {judge.get_call_log()}")

    with open('tests/experiments/results_exp_b.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    assert len(results) == N


# ── Experimento C — Isolar Variância do Bandit ────────────────────────────────

def test_experiment_c_bandit_variance(mock_optimizer_factory):
    """Experimento C: 10 execuções com juiz determinístico — isola bandit.

    Com o juiz fixo (DeterministicJudge), qualquer variância restante
    vem exclusivamente do bandit (escolha estocástica de estratégia)
    e da ordem de expansão do MCTS.
    """
    N = 10
    ITER = 5
    results = []

    # Configurar agent mock para gerar skills com marcadores de estratégia
    def _make_agent_mock_for_strategy(strategy_label: str):
        agent = MagicMock()
        if strategy_label == 'mutador_cognitivo':
            text = (
                "## Raciocínio\nPremissas: análise.\n"
                "Deduções: melhoria estrutural.\n"
                "Conclusão: aplicar.\n\n"
                "## Regras\n1. Regra A\n2. Regra B\n\n"
                "## Conclusão\nResultado esperado."
            )
        elif strategy_label == 'simplificar':
            text = "Simplified version of the instruction. Simpler and clearer."
        else:
            text = f"Mutated instruction using {strategy_label} approach."
        agent.nova_instrucao = text
        agent.critica = f"Crítica ({strategy_label})"
        return MagicMock(return_value=agent)

    for run_i in range(N):
        # Cria juiz determinístico com rewards conhecidos por estratégia
        judge = DeterministicJudge({
            'mutador_cognitivo': 0.85,
            'simplificar': 0.70,
            'adicionar_exemplos': 0.75,
            'detalhar_passos': 0.72,
            'default': 0.65,
        })

        result = _run_single_optimize(
            mock_optimizer_factory,
            SKILL_BASE,
            ITER,
            avaliador_modo_b=judge,
            agent_mock=_make_agent_mock_for_strategy('simplificar'),
            agent_cognitivo_mock=_make_agent_mock_for_strategy('mutador_cognitivo'),
        )
        result['run'] = run_i
        result['judge_calls'] = judge.get_call_log()
        results.append(result)

    rewards = [r['best_reward'] for r in results]
    scores = [r['best_score'] for r in results]

    print("\n=== Experiment C: Bandit Variance (Deterministic Judge) ===")
    print(f"  N={N}, iterations={ITER}")
    print(f"  best_reward: mean={statistics.mean(rewards):.3f}, "
          f"stdev={statistics.stdev(rewards):.3f}, "
          f"min-max=[{min(rewards):.3f}, {max(rewards):.3f}]")
    print(f"  best_score:  mean={statistics.mean(scores):.3f}, "
          f"stdev={statistics.stdev(scores):.3f}")
    print("  first_3_strategies por run:")
    for r in results:
        print(f"    run {r['run']}: {r['first_3_strategies']}")

    with open('tests/experiments/results_exp_c.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    assert len(results) == N