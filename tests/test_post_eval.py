"""Testes para avaliação pós-implementação (_run_post_eval) e expansão com composição."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.domain.config import MCTSConfig
from src.domain.mcts import MCTSNode
from src.signatures import AvaliacaoModoB


# ── SubTask 6.1: Avaliação pós-implementação ──────────────────────────────────

class TestPostEval:
    @pytest.fixture
    def optimizer_with_post_eval(self, mock_optimizer_factory):
        """Cria um Optimizer com avaliador_modo_b mockado explicitamente."""
        opt = mock_optimizer_factory(skill_original="Skill original de teste")
        opt.config = MCTSConfig(
            max_iterations=100, c_param=1.41, gamma=0.95,
            progressive_alpha=1.0, progressive_c=10.0, value_threshold=0.3,
            value_lr=0.1, bandit_c_param=1.41, bandit_temperature=2.0,
            bandit_temperature_decay=0.95, semantic_sim_threshold=0.92,
            lexical_density_min=0.35, verbosity_penalty_factor=0.7,
            buzzword_threshold=3, cognitivo_prior_count=2,
            cognitivo_prior_mean_delta=0.05, density_threshold=0.9,
            density_multiplier_min=0.8, density_multiplier_max=1.2,
            density_structured_bonus=0.05, reward_floor=0.30,
            post_eval_margin_min=0.05, post_eval_sample_size=5,
        )
        return opt

    def _mock_avaliacao(self, manteve_regras=True, defeitos=None, notas=80.0):
        """Cria uma mock AvaliacaoModoB com os parâmetros dados."""
        if defeitos is None:
            defeitos = []
        return AvaliacaoModoB(
            manteve_regras_criticas=manteve_regras,
            nota_clareza=notas,
            nota_formatacao=notas,
            nota_robustez=notas,
            nota_densidade_informacional=notas,
            nota_acionabilidade=notas,
            nota_anti_fragilidade=notas,
            feedback_detalhado='Mock feedback.',
            defeitos_encontrados=defeitos,
        )

    def test_post_eval_approves_behavioral_improvement(self, optimizer_with_post_eval):
        """Mock do avaliador_modo_b retorna manteve_regras_criticas=True,
        0 defeitos para mutada e 3 defeitos para original → approved=True."""
        opt = optimizer_with_post_eval

        mock_avaliador = MagicMock()
        mock_avaliador.side_effect = [
            self._mock_avaliacao(manteve_regras=True, defeitos=['def1', 'def2', 'def3']),  # original: 3 defeitos
            self._mock_avaliacao(manteve_regras=True, defeitos=[]),  # mutada: 0 defeitos
        ]
        opt.avaliador_modo_b = mock_avaliador

        # Cria casos de teste mockados
        case = MagicMock()
        case.parent_instruction = "parent instruction"
        case.instruction = "original instruction"
        case.feedback = "feedback de teste"

        approved, mean_orig, mean_mut, avg_def_orig, avg_def_mut = opt._run_post_eval(
            "instruction_original", "instruction_mutada", [case]
        )

        assert approved, "Post-Eval deveria aprovar melhoria comportamental (0 vs 3 defeitos)"
        # orig: manteve_regras=True, 3 defeitos → penalty=0.3, score=0.7
        # mut: manteve_regras=True, 0 defeitos → penalty=0.0, score=1.0
        assert mean_mut > mean_orig, f"Score mutada ({mean_mut:.3f}) deveria ser maior que original ({mean_orig:.3f})"
        assert avg_def_mut < avg_def_orig

    def test_post_eval_rejects_no_improvement(self, optimizer_with_post_eval):
        """Mock retorna mesmos valores para ambas → approved=False (delta <= 0)."""
        opt = optimizer_with_post_eval

        mock_avaliador = MagicMock()
        mock_avaliador.side_effect = [
            self._mock_avaliacao(manteve_regras=True, defeitos=[]),  # original: 0 defeitos
            self._mock_avaliacao(manteve_regras=True, defeitos=[]),  # mutada: 0 defeitos
        ]
        opt.avaliador_modo_b = mock_avaliador

        case = MagicMock()
        case.parent_instruction = "parent instruction"
        case.instruction = "original instruction"
        case.feedback = "feedback de teste"

        approved, mean_orig, mean_mut, _, _ = opt._run_post_eval(
            "instruction_original", "instruction_mutada", [case]
        )

        assert not approved, "Post-Eval deveria rejeitar quando não há melhoria (delta=0)"

    def test_post_eval_rejects_critical_rules_broken(self, optimizer_with_post_eval):
        """Mutada tem manteve_regras_criticas=False → score=0."""
        opt = optimizer_with_post_eval

        mock_avaliador = MagicMock()
        mock_avaliador.side_effect = [
            self._mock_avaliacao(manteve_regras=True, defeitos=[]),   # original: OK
            self._mock_avaliacao(manteve_regras=False, defeitos=[]),  # mutada: quebrou regras críticas
        ]
        opt.avaliador_modo_b = mock_avaliador

        case = MagicMock()
        case.parent_instruction = "parent instruction"
        case.instruction = "original instruction"
        case.feedback = "feedback de teste"

        approved, mean_orig, mean_mut, _, _ = opt._run_post_eval(
            "instruction_original", "instruction_mutada", [case]
        )

        # mutada com manteve_regras_criticas=False → score 0.0
        assert mean_mut == 0.0, f"Score da mutada deveria ser 0.0 (regras críticas quebradas), mas foi {mean_mut:.3f}"
        assert not approved, "Post-Eval deveria rejeitar mutação que quebra regras críticas"

    def test_post_eval_empty_cases_approves(self, optimizer_with_post_eval):
        """Sem casos de teste → approved=True (warm-up)."""
        opt = optimizer_with_post_eval

        approved, mean_orig, mean_mut, avg_def_orig, avg_def_mut = opt._run_post_eval(
            "instruction_original", "instruction_mutada", []
        )

        assert approved, "Post-Eval deveria aprovar sem casos de teste (warm-up)"
        assert mean_orig == 0.0
        assert mean_mut == 0.0


# ── SubTask 6.3: expand_node com composição ────────────────────────────────────

class TestExpandNodeComposite:
    @pytest.fixture
    def opt_with_composite_bandit(self, mock_optimizer_factory):
        """Cria um Optimizer cujo bandit retorna composição e o agent mockado gera output válido."""
        opt = mock_optimizer_factory(skill_original="Skill original de teste")
        opt.config = MCTSConfig(
            max_iterations=100, c_param=1.41, gamma=0.95,
            progressive_alpha=1.0, progressive_c=10.0, value_threshold=0.3,
            value_lr=0.1, bandit_c_param=1.41, bandit_temperature=2.0,
            bandit_temperature_decay=0.95, semantic_sim_threshold=0.92,
            lexical_density_min=0.35, verbosity_penalty_factor=0.7,
            buzzword_threshold=3, cognitivo_prior_count=2,
            cognitivo_prior_mean_delta=0.05, density_threshold=0.9,
            density_multiplier_min=0.8, density_multiplier_max=1.2,
            density_structured_bonus=0.05, reward_floor=0.30,
            post_eval_margin_min=0.0,  # margem zero para não rejeitar
            post_eval_sample_size=5,
            ab_margin_min=0.0,  # margem zero para não rejeitar no gate A/B
        )
        return opt

    def _mock_agent_output(self, nova_instrucao="Instrução mutada composta"):
        """Cria um mock de output de agente que retorna a instrução dada."""
        mock_predicao = MagicMock()
        mock_predicao.nova_instrucao = nova_instrucao
        mock_predicao.critica = "Crítica de teste"
        return mock_predicao

    def _mock_avaliacao_aprovada(self):
        """Cria um mock de avaliador que sempre aprova."""
        return AvaliacaoModoB(
            manteve_regras_criticas=True,
            nota_clareza=85.0,
            nota_formatacao=85.0,
            nota_robustez=85.0,
            nota_densidade_informacional=85.0,
            nota_acionabilidade=85.0,
            nota_anti_fragilidade=85.0,
            feedback_detalhado='Mock feedback.',
            defeitos_encontrados=[],
        )

    def test_expand_node_applies_composite_sequentially(self, opt_with_composite_bandit):
        """Mock do bandit retorna lista, verifica que mutation_strategy do child
        é composite:... e que o agente foi chamado para cada estratégia da composição."""
        opt = opt_with_composite_bandit

        composite_list = ['compressao_formalizacao', 'enriquecimento_exemplos']
        opt.mutation_bandit.select = MagicMock(return_value=composite_list)

        # Mock do agente para retornar outputs diferentes a cada chamada
        opt.agent = MagicMock(side_effect=[
            self._mock_agent_output("Instrução após compressão"),
            self._mock_agent_output("Instrução composta final"),
        ])
        opt.avaliador_modo_b = MagicMock(return_value=self._mock_avaliacao_aprovada())

        # Mock do experience store para gate A/B e post-eval
        opt.experience_store.get_ab_test_cases = MagicMock(return_value=[])

        leaf = MCTSNode(instruction="Instrução original")
        leaf.visits = 1
        leaf.q_value = 0.5

        # Mock _should_prune para não podar
        opt._should_prune = MagicMock(return_value=False)

        child = opt._expand_node(leaf)

        # Verifica que a mutation_strategy do child é composite
        expected_key = f"composite:{'+'.join(composite_list)}"
        assert child.mutation_strategy == expected_key, \
            f"Esperado '{expected_key}', obtido '{child.mutation_strategy}'"

        # O agente deve ter sido chamado pelo menos uma vez (uma por estratégia)
        assert opt.agent.call_count >= 1, "Agente deveria ter sido chamado para cada estratégia da composição"

    def test_expand_node_registers_composite_mutation_strategy(self, opt_with_composite_bandit):
        """Verifica formato da mutation_strategy no child node criado por composição."""
        opt = opt_with_composite_bandit

        composite_list = ['mutador_cognitivo', 'compressao_formalizacao']
        opt.mutation_bandit.select = MagicMock(return_value=composite_list)

        opt.agent = MagicMock(return_value=self._mock_agent_output("Instrução composta"))
        opt.avaliador_modo_b = MagicMock(return_value=self._mock_avaliacao_aprovada())
        opt.experience_store.get_ab_test_cases = MagicMock(return_value=[])
        opt._should_prune = MagicMock(return_value=False)

        leaf = MCTSNode(instruction="Instrução original")
        leaf.visits = 1
        leaf.q_value = 0.5

        child = opt._expand_node(leaf)

        # Verifica o formato: composite:estrat1+estrat2
        assert child.mutation_strategy.startswith("composite:"), \
            "mutation_strategy deveria começar com 'composite:'"
        assert '+'.join(composite_list) in child.mutation_strategy, \
            "mutation_strategy deveria conter as chaves das estratégias"


# ── SubTask 6.4: Rejeição no post-eval após gate A/B ───────────────────────────

class TestPostEvalRejectionAfterAB:
    @pytest.fixture
    def opt_for_rejection(self, mock_optimizer_factory):
        """Cria um Optimizer com gate A/B permissivo e post-eval restritivo."""
        opt = mock_optimizer_factory(skill_original="Skill original de teste")
        opt.config = MCTSConfig(
            max_iterations=100, c_param=1.41, gamma=0.95,
            progressive_alpha=1.0, progressive_c=10.0, value_threshold=0.3,
            value_lr=0.1, bandit_c_param=1.41, bandit_temperature=2.0,
            bandit_temperature_decay=0.95, semantic_sim_threshold=0.92,
            lexical_density_min=0.35, verbosity_penalty_factor=0.7,
            buzzword_threshold=3, cognitivo_prior_count=2,
            cognitivo_prior_mean_delta=0.05, density_threshold=0.9,
            density_multiplier_min=0.8, density_multiplier_max=1.2,
            density_structured_bonus=0.05, reward_floor=0.30,
            ab_margin_min=0.0,  # Gate A/B sempre aprova (delta >= 0)
            post_eval_margin_min=0.10,  # Post-eval exige melhoria
            post_eval_sample_size=5,
        )
        return opt

    def test_mutation_rejected_by_post_eval_after_ab_gate(self, opt_for_rejection):
        """Gate A/B aprova mas post-eval reprova → nó filho não é criado."""
        opt = opt_for_rejection

        # Bandit retorna estratégia isolada (não composição)
        opt.mutation_bandit.select = MagicMock(return_value='compressao_formalizacao')

        # Mock do agente: gera output válido
        opt.agent = MagicMock(return_value=MagicMock(
            nova_instrucao="Instrução mutada que será rejeitada",
            critica="Crítica de teste",
        ))
        opt._should_prune = MagicMock(return_value=False)

        # Mock do avaliador para o post-eval: mutada quebra regras críticas
        opt.avaliador_modo_b = MagicMock(return_value=AvaliacaoModoB(
            manteve_regras_criticas=False,  # <-- REJEITADO
            nota_clareza=80.0,
            nota_formatacao=80.0,
            nota_robustez=80.0,
            nota_densidade_informacional=80.0,
            nota_acionabilidade=80.0,
            nota_anti_fragilidade=80.0,
            feedback_detalhado='Mock feedback.',
            defeitos_encontrados=['violação crítica'],
        ))

        # Mock do experience store: retorna casos para gate A/B e post-eval
        case = MagicMock()
        case.parent_instruction = "parent instruction"
        case.instruction = "original instruction"
        case.feedback = "feedback de teste"
        opt.experience_store.get_ab_test_cases = MagicMock(return_value=[case])

        leaf = MCTSNode(instruction="Instrução original")
        leaf.visits = 1
        leaf.q_value = 0.5

        child = opt._expand_node(leaf)

        # O nó folha não deve ter sido expandido com sucesso
        # Quando todas as tentativas falham, _expand_node retorna o próprio leaf
        assert child == leaf, \
            "Nó filho NÃO deveria ser criado quando post-eval reprova após gate A/B aprovar"

        # Verifica que a estratégia foi registrada como falha
        assert 'compressao_formalizacao' in leaf.tried_strategies, \
            "Estratégia deveria estar em tried_strategies após falha"
        assert opt._expansion_failure.get('compressao_formalizacao', 0) > 0, \
            "Falha de expansão deveria ser registrada"
