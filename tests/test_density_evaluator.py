from src.density_evaluator import calculate_density_multiplier, _has_structured_fields


def test_compression_boost():
    mult = calculate_density_multiplier(child_instruction="abc", parent_instruction="abcdef")
    assert mult == 1.5


def test_verbosity_penalty():
    mult = calculate_density_multiplier(child_instruction="abcdef", parent_instruction="abc")
    assert mult == 0.5


def test_equal_length_no_change():
    mult = calculate_density_multiplier(child_instruction="abcdef", parent_instruction="abcdef")
    assert mult == 1.0


def test_empty_parent_fallback():
    mult = calculate_density_multiplier(child_instruction="abc", parent_instruction="")
    assert mult == 0.5


def test_empty_child():
    mult = calculate_density_multiplier(child_instruction="", parent_instruction="abcdef")
    assert mult == 1.5


def test_structured_bonus_cognitivo():
    child = "## Raciocínio\npremissas\n## Regras\nregras\n## Conclusão\nconc"
    parent = "x" * len(child)
    mult = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=parent,
        mutation_strategy="mutador_cognitivo",
    )
    assert mult == 1.2


def test_structured_bonus_non_cognitivo():
    child = "## Raciocínio\npremissas\n## Regras\nregras\n## Conclusão\nconc"
    parent = "x" * len(child)
    mult = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=parent,
        mutation_strategy="outra",
    )
    assert mult == 1.0


def test_structured_bonus_cognitivo_no_headings():
    child = "plain text without any cognitive headings"
    parent = "x" * len(child)
    mult = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=parent,
        mutation_strategy="mutador_cognitivo",
    )
    assert mult == 1.0


def test_custom_threshold():
    mult = calculate_density_multiplier(
        child_instruction="abcdef", parent_instruction="abcdef", density_threshold=0.8
    )
    assert mult == 0.8


def test_custom_bounds():
    mult = calculate_density_multiplier(
        child_instruction="abc",
        parent_instruction="abcdef",
        density_multiplier_min=0.7,
        density_multiplier_max=1.3,
    )
    assert mult == 1.3


def test_has_all_headings():
    instruction = "Some text\n## Raciocínio\ncontent\n## Regras\ncontent\n## Conclusão\ncontent"
    assert _has_structured_fields(instruction) is True


def test_has_missing_one_heading():
    instruction = "Some text\n## Raciocínio\ncontent\n## Regras\ncontent"
    assert _has_structured_fields(instruction) is False


def test_has_no_headings():
    instruction = "plain text without any cognitive sections"
    assert _has_structured_fields(instruction) is False


def test_has_headings_case_insensitive():
    instruction = "Some text\n## RACIOCÍNIO\ncontent\n## REGRAS\ncontent\n## CONCLUSÃO\ncontent"
    assert _has_structured_fields(instruction) is True
