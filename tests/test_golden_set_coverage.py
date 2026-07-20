"""Teste de cobertura do golden set — Fase 5 (LLMBar)."""
import pytest
from src.drift.golden import GoldenSet
from src.drift.models import GoldenProbe


REQUIRED_CATEGORIES = ['estilo', 'natural', 'constraint', 'manual', 'negation']
MIN_PROBES_PER_CATEGORY = 1


@pytest.fixture
def golden():
    return GoldenSet()


def test_golden_set_not_empty(golden):
    assert not golden.is_empty(), "Golden set nao pode estar vazio em producao."


def test_all_probes_have_expected_fields(golden):
    for probe in golden.probes:
        assert probe.id, f"Probe sem id: {probe}"
        assert probe.skill_original, f"Probe {probe.id} sem skill_original"
        assert probe.skill_otimizada, f"Probe {probe.id} sem skill_otimizada"
        assert probe.expected_rank_band in ('alto', 'medio', 'baixo'), \
            f"Probe {probe.id} rank_band invalido: {probe.expected_rank_band}"
        assert probe.category, f"Probe {probe.id} sem category"


def test_required_categories_present(golden):
    present_cats = set(p.category for p in golden.probes)
    missing = [c for c in REQUIRED_CATEGORIES if c not in present_cats]
    assert not missing, f"Categorias obrigatorias ausentes: {missing}"


def test_min_probes_per_category(golden):
    from collections import Counter
    cat_counts = Counter(p.category for p in golden.probes)
    for cat in REQUIRED_CATEGORIES:
        count = cat_counts.get(cat, 0)
        assert count >= MIN_PROBES_PER_CATEGORY, \
            f"Categoria '{cat}' tem apenas {count} probe(s), minimo esperado: {MIN_PROBES_PER_CATEGORY}"


def test_rank_bands_consistent_with_composite(golden):
    """
    Verifica que as rank_bands sao consistentes com os composite scores esperados.
    Alto > medio > baixo entre probes da mesma categoria.
    """
    for cat in REQUIRED_CATEGORIES:
        probes_in_cat = [p for p in golden.probes if p.category == cat]
        if len(probes_in_cat) < 2:
            continue
        for p in probes_in_cat:
            if p.expected_rank_band == 'alto':
                for q in probes_in_cat:
                    if q.expected_rank_band == 'medio':
                        assert p.expected.composite_score() > q.expected.composite_score(), \
                            f"{p.id} (alto, {p.expected.composite_score():.3f}) deveria > {q.id} (medio, {q.expected.composite_score():.3f})"
                    elif q.expected_rank_band == 'baixo':
                        assert p.expected.composite_score() > q.expected.composite_score(), \
                            f"{p.id} (alto, {p.expected.composite_score():.3f}) deveria > {q.id} (baixo, {q.expected.composite_score():.3f})"


def test_composite_scores_in_range(golden):
    for probe in golden.probes:
        cs = probe.expected.composite_score()
        assert 0.0 <= cs <= 1.0, f"Probe {probe.id} composite score fora do range: {cs:.3f}"


def test_style_gap_probes_present(golden):
    """SD-1 e SD-3 devem existir para calcular style_gap."""
    ids = [p.id for p in golden.probes]
    assert 'SD-1' in ids, "SD-1 ausente — style_gap nao pode ser calculado"
    assert 'SD-3' in ids, "SD-3 ausente — style_gap nao pode ser calculado"


def test_hard_gate_probe_present(golden):
    """SD-2 deve existir como hard-gate probe."""
    ids = [p.id for p in golden.probes]
    assert 'SD-2' in ids, "SD-2 ausente — hard-gate probe necessario"


def test_all_probes_have_verifier(golden):
    for probe in golden.probes:
        assert probe.verifier, f"Probe {probe.id} sem verifier descritivo"