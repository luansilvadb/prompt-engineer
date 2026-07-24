"""Testes dos quatro eixos de mutação e do gate A/B empírico."""
import pytest
from unittest.mock import MagicMock, patch

from src.mutation_strategies.registry import StrategyRegistry
from src.experience_store_sqlite import SqliteExperienceStore
from src.experience_store import Experience


# ── Task 5.1: Registry contém 5 estratégias ──────────────────────────────────

class TestRegistryMutationAxes:
    def test_registry_has_five_strategies(self):
        registry = StrategyRegistry()
        keys = set(registry.get_all_keys())
        expected = {
            'mutador_cognitivo',
            'compressao_formalizacao',
            'enriquecimento_exemplos',
            'reorganizacao_falha',
            'preservacao_blocos',
        }
        assert expected.issubset(keys), f"Faltam estratégias: {expected - keys}"

    def test_compression_strategy_has_prompt(self):
        registry = StrategyRegistry()
        assert registry.get_name('compressao_formalizacao') == 'Compressão e Formalização'
        prompt = registry.get_prompt('compressao_formalizacao')
        assert prompt and len(prompt) > 20
        assert 'redund' in prompt.lower() or 'comprim' in prompt.lower()

    def test_enrichment_strategy_has_prompt(self):
        registry = StrategyRegistry()
        assert registry.get_name('enriquecimento_exemplos') == 'Enriquecimento com Exemplos'
        prompt = registry.get_prompt('enriquecimento_exemplos')
        assert prompt and len(prompt) > 20
        assert 'exemplo' in prompt.lower()

    def test_reorganization_strategy_has_prompt(self):
        registry = StrategyRegistry()
        assert registry.get_name('reorganizacao_falha') == 'Reorganização por Prioridade de Falha'
        prompt = registry.get_prompt('reorganizacao_falha')
        assert prompt and len(prompt) > 20
        assert 'reord' in prompt.lower() or 'prioridad' in prompt.lower() or 'falha' in prompt.lower()

    def test_preservation_strategy_has_prompt(self):
        registry = StrategyRegistry()
        assert registry.get_name('preservacao_blocos') == 'Preservação Seletiva de Blocos'
        prompt = registry.get_prompt('preservacao_blocos')
        assert prompt and len(prompt) > 20
        assert 'preserv' in prompt.lower() or 'blocos' in prompt.lower()


# ── Task 5.3: Métodos do Experience Store ─────────────────────────────────────

class TestExperienceStoreNewMethods:
    @pytest.fixture
    def store(self):
        return SqliteExperienceStore(db_path=":memory:", max_experiences=500)

    def _add_exp(self, store, delta, feedback, instruction="instr", mutation_strategy="ms"):
        store.add(Experience(
            skill_hash="hash1",
            mutation_strategy=mutation_strategy,
            delta_reward=delta,
            absolute_reward=0.5,
            feedback=feedback,
            parent_instruction_hash="",
            instruction=instruction,
            parent_instruction="parent",
        ))

    def test_get_feedback_frequency_returns_worst_first(self, store):
        self._add_exp(store, -0.2, "Erro A", "i1")
        self._add_exp(store, 0.3, "Sucesso B", "i2")
        self._add_exp(store, -0.5, "Erro C", "i3")
        results = store.get_feedback_frequency(top_k=5)
        assert len(results) > 0
        # Piores delta resultado primeiro
        assert results[0]['delta_reward'] <= results[-1]['delta_reward']
        assert 'feedback' in results[0]
        assert 'count' in results[0]

    def test_get_effective_blocks_returns_positive_only(self, store):
        self._add_exp(store, 0.3, "ok", "instr_boa")
        self._add_exp(store, -0.1, "ruim", "instr_ruim")
        results = store.get_effective_blocks(top_k=5)
        assert all(r['delta_reward'] > 0 for r in results)
        assert results[0]['delta_reward'] >= results[-1]['delta_reward']

    def test_get_effective_blocks_truncates_instruction(self, store):
        long_instr = "x" * 1000
        self._add_exp(store, 0.5, "ok", long_instr)
        results = store.get_effective_blocks(top_k=5)
        assert all(len(r['instruction']) <= 500 for r in results)

    def test_get_ab_test_cases_returns_experiences(self, store):
        self._add_exp(store, 0.1, "feedback1", "i1")
        self._add_exp(store, 0.2, "feedback2", "i2")
        self._add_exp(store, 0.1, "no_feedback" if False else "feedback3", "i3")
        results = store.get_ab_test_cases(skill_hash="hash1", top_k=10)
        assert len(results) > 0
        assert all(isinstance(e, Experience) for e in results)
        assert all(e.feedback != '' for e in results)

    def test_get_ab_test_cases_filters_by_skill_hash(self, store):
        self._add_exp(store, 0.1, "fb", "i1")
        store.add(Experience(
            skill_hash="other_hash",
            mutation_strategy="ms",
            delta_reward=0.1,
            absolute_reward=0.5,
            feedback="other",
            instruction="other_i",
            parent_instruction="parent",
        ))
        results = store.get_ab_test_cases(skill_hash="hash1", top_k=10)
        assert all(e.skill_hash == "hash1" for e in results)


# ── Task 5.2: Gate A/B ─────────────────────────────────────────────────────────

class TestABGate:
    def test_ab_gate_approves_superior_mutation(self, mock_optimizer_factory):
        """Gate A/B aprova mutação com score superior ao original + margem."""
        opt = mock_optimizer_factory()

        # Mock funcao_de_recompensa: original sempre 0.3, mutada sempre 0.6
        with patch('src.optimizer.funcao_de_recompensa') as mock_reward:
            call_count = [0]
            def side_effect(**kwargs):
                call_count[0] += 1
                is_original = call_count[0] % 2 == 1  # alterna: original primeiro
                if is_original:
                    return 0.3, "original feedback"
                return 0.6, "mutada feedback"
            mock_reward.side_effect = side_effect

            cases = [MagicMock(parent_instruction="parent", instruction="orig", feedback="fb")]
            approved, score_orig, score_mut = opt._run_ab_gate(
                "instruction_original", "instruction_mutada", cases
            )
            assert approved, "Gate deveria aprovar mutação superior"
            assert score_mut > score_orig

    def test_ab_gate_rejects_inferior_mutation(self, mock_optimizer_factory):
        """Gate A/B rejeita mutação com score inferior ao original."""
        opt = mock_optimizer_factory()

        with patch('src.optimizer.funcao_de_recompensa') as mock_reward:
            call_count = [0]
            def side_effect(**kwargs):
                call_count[0] += 1
                is_original = call_count[0] % 2 == 1
                if is_original:
                    return 0.7, "original feedback"
                return 0.4, "mutada feedback"
            mock_reward.side_effect = side_effect

            cases = [MagicMock(parent_instruction="parent", instruction="orig", feedback="fb")]
            approved, score_orig, score_mut = opt._run_ab_gate(
                "instruction_original", "instruction_mutada", cases
            )
            assert not approved, "Gate deveria rejeitar mutação inferior"

    def test_ab_gate_rejects_within_margin(self, mock_optimizer_factory):
        """Gate A/B rejeita melhoria menor que a margem mínima (0.05)."""
        opt = mock_optimizer_factory()
        assert opt.config.ab_margin_min == 0.05

        with patch('src.optimizer.funcao_de_recompensa') as mock_reward:
            call_count = [0]
            def side_effect(**kwargs):
                call_count[0] += 1
                is_original = call_count[0] % 2 == 1
                if is_original:
                    return 0.50, "fb"
                return 0.53, "fb"  # delta=0.03 < 0.05
            mock_reward.side_effect = side_effect

            cases = [MagicMock(parent_instruction="parent", instruction="orig", feedback="fb")]
            approved, _, _ = opt._run_ab_gate("orig", "mut", cases)
            assert not approved, "Delta 0.03 < margem 0.05 → rejeitar"

    def test_ab_gate_approved_without_cases(self, mock_optimizer_factory):
        """Gate A/B aprova warm-up sem casos de feedback."""
        opt = mock_optimizer_factory()
        approved, _, _ = opt._run_ab_gate("orig", "mut", [])
        assert approved


# ── Injeção de dados dinâmicos ──────────────────────────────────────────────────

class TestDynamicDataInjection:
    def test_reorganization_gets_error_data(self, mock_optimizer_factory):
        opt = mock_optimizer_factory()
        # Adiciona feedbacks negativos no store
        opt.experience_store.add(Experience(
            skill_hash="hash", mutation_strategy="ms", delta_reward=-0.3,
            absolute_reward=0.2, feedback="Erro crítico detectado",
            instruction="i1", parent_instruction="p1"
        ))
        prompt = opt._inject_dynamic_data('reorganizacao_falha', 'Prompt base.')
        assert 'ERRO' in prompt.upper() or 'FALHA' in prompt.upper()
        assert 'Erro crítico' in prompt or 'erro' in prompt.lower()

    def test_preservation_gets_effective_blocks(self, mock_optimizer_factory):
        opt = mock_optimizer_factory()
        opt.experience_store.add(Experience(
            skill_hash="hash", mutation_strategy="ms", delta_reward=0.4,
            absolute_reward=0.8, feedback="Sucesso",
            instruction="Bloco eficaz X", parent_instruction="p1"
        ))
        prompt = opt._inject_dynamic_data('preservacao_blocos', 'Prompt base.')
        assert 'BLOCO' in prompt.upper() or 'PRESERVAR' in prompt.upper()
        assert 'Bloco eficaz X' in prompt

    def test_compression_no_injection(self, mock_optimizer_factory):
        """Estratégias de compressão e enriquecimento não recebem dados dinâmicos."""
        opt = mock_optimizer_factory()
        original_prompt = 'Prompt estático.'
        prompt = opt._inject_dynamic_data('compressao_formalizacao', original_prompt)
        assert prompt == original_prompt
        prompt = opt._inject_dynamic_data('enriquecimento_exemplos', original_prompt)
        assert prompt == original_prompt
