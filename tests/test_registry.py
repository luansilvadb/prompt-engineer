from src.mutation_strategies.registry import StrategyRegistry


def test_seed_registered():
    registry = StrategyRegistry()
    assert 'mutador_cognitivo' in registry.get_all_keys()


def test_seed_prompt_content():
    registry = StrategyRegistry()
    prompt = registry.get_prompt('mutador_cognitivo')
    assert prompt
    assert 'premissas' in prompt.lower()


def test_seed_name():
    registry = StrategyRegistry()
    assert registry.get_name('mutador_cognitivo') == 'Mutador Cognitivo'


def test_seed_idempotent():
    registry = StrategyRegistry()
    from unittest.mock import MagicMock
    registry.save = MagicMock()
    registry._seed_hardcoded_strategies()
    registry.save.assert_not_called()


# ── SubTask 6.6: build_composite_prompt ────────────────────────────────────────

class TestBuildCompositePrompt:
    @staticmethod
    def _make_registry():
        """Cria um registry populado com as estratégias padrão."""
        registry = StrategyRegistry()
        return registry

    def test_build_composite_prompt_generates_correct_key(self):
        """composite_key no formato composite:estrat1+estrat2."""
        registry = self._make_registry()
        keys = ['mutador_cognitivo', 'compressao_formalizacao']

        composite_key, composite_name, composite_prompt = registry.build_composite_prompt(keys)

        expected_key = 'composite:mutador_cognitivo+compressao_formalizacao'
        assert composite_key == expected_key, (
            f"Esperado '{expected_key}', obtido '{composite_key}'"
        )
        assert composite_key.startswith('composite:'), "Chave composta deve começar com 'composite:'"

    def test_build_composite_prompt_generates_readable_name(self):
        """Nome contém os nomes das estratégias."""
        registry = self._make_registry()
        keys = ['mutador_cognitivo', 'enriquecimento_exemplos']

        composite_key, composite_name, composite_prompt = registry.build_composite_prompt(keys)

        assert 'Mutador Cognitivo' in composite_name, (
            f"Nome deveria conter 'Mutador Cognitivo', obtido: '{composite_name}'"
        )
        assert 'Enriquecimento com Exemplos' in composite_name, (
            f"Nome deveria conter 'Enriquecimento com Exemplos', obtido: '{composite_name}'"
        )
        assert composite_name.startswith('Composição:'), (
            f"Nome deveria começar com 'Composição:', obtido: '{composite_name}'"
        )
        assert ' + ' in composite_name, "Nome deveria conter ' + ' entre as estratégias"

    def test_build_composite_prompt_concatenates_prompts(self):
        """Prompt contém prompts de ambas estratégias."""
        registry = self._make_registry()
        keys = ['compressao_formalizacao', 'enriquecimento_exemplos']

        composite_key, composite_name, composite_prompt = registry.build_composite_prompt(keys)

        prompt_compressao = registry.get_prompt('compressao_formalizacao')
        prompt_enriquecimento = registry.get_prompt('enriquecimento_exemplos')

        assert len(composite_prompt) >= len(prompt_compressao) + len(prompt_enriquecimento), (
            "Prompt composto deve conter ambos os prompts concatenados"
        )
        # Verifica que o separador está presente
        assert '--- PRÓXIMA ESTRATÉGIA ---' in composite_prompt, (
            "Prompt composto deve ter separador '--- PRÓXIMA ESTRATÉGIA ---'"
        )
        # Verifica trechos de cada prompt
        assert 'comprim' in composite_prompt.lower() or 'redund' in composite_prompt.lower(), (
            "Prompt composto deve conter conteúdo da estratégia de compressão"
        )
        assert 'exemplo' in composite_prompt.lower(), (
            "Prompt composto deve conter conteúdo da estratégia de enriquecimento"
        )

    def test_static_get_composite_key(self):
        """get_composite_key estático gera chave correta."""
        keys = ['estrat_a', 'estrat_b', 'estrat_c']
        result = StrategyRegistry.get_composite_key(keys)
        assert result == 'composite:estrat_a+estrat_b+estrat_c'

    def test_composite_name_method(self):
        """composite_name gera nome legível."""
        registry = self._make_registry()
        keys = ['mutador_cognitivo', 'compressao_formalizacao']
        name = registry.composite_name(keys)
        assert name.startswith('Composição:')
        assert 'Mutador Cognitivo' in name
        assert 'Compressão e Formalização' in name

    def test_get_prompt_for_composite_key_resolves(self):
        """get_prompt para chave composite: deve resolver dinamicamente."""
        registry = self._make_registry()
        # Cria uma chave composta que NÃO está no registry
        composite_key = 'composite:mutador_cognitivo+compressao_formalizacao'
        prompt = registry.get_prompt(composite_key)
        assert len(prompt) > 0, "get_prompt deve resolver prompt para chave composta"
        assert 'premissas' in prompt.lower() or 'comprim' in prompt.lower(), (
            "Prompt deve conter conteúdo de ao menos uma das estratégias"
        )

    def test_get_name_for_composite_key_resolves(self):
        """get_name para chave composite: deve resolver dinamicamente."""
        registry = self._make_registry()
        composite_key = 'composite:mutador_cognitivo+enriquecimento_exemplos'
        name = registry.get_name(composite_key)
        assert 'Mutador Cognitivo' in name
        assert 'Enriquecimento com Exemplos' in name
        assert name.startswith('Composição:')
