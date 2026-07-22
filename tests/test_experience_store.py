import pytest
import time
from unittest.mock import patch
from src.experience_store import (
    Experience,
    _tokenize,
    _compute_tf,
    _compute_idf,
    _cosine_similarity,
    hash_instruction,
)
from src.experience_store_sqlite import SqliteExperienceStore


def test_experience_model():
    exp = Experience(
        skill_hash="hash1",
        mutation_strategy="mut_strat",
        delta_reward=0.5,
        absolute_reward=1.5,
        feedback="This is a feedback",
        timestamp=100.0,
        parent_instruction_hash="hash0",
        instruction="new inst",
        parent_instruction="old inst"
    )

    d = exp.to_dict()
    assert d['skill_hash'] == "hash1"
    assert d['mutation_strategy'] == "mut_strat"
    assert d['delta_reward'] == 0.5
    assert d['absolute_reward'] == 1.5
    assert d['feedback'] == "This is a feedback"
    assert d['timestamp'] == 100.0
    assert d['parent_instruction_hash'] == "hash0"
    assert d['instruction'] == "new inst"
    assert d['parent_instruction'] == "old inst"

    exp2 = Experience.from_dict(d)
    assert exp2.skill_hash == exp.skill_hash
    assert exp2.mutation_strategy == exp.mutation_strategy
    assert exp2.delta_reward == exp.delta_reward
    assert exp2.absolute_reward == exp.absolute_reward
    assert exp2.feedback == exp.feedback
    assert exp2.timestamp == exp.timestamp
    assert exp2.parent_instruction_hash == exp.parent_instruction_hash
    assert exp2.instruction == exp.instruction
    assert exp2.parent_instruction == exp.parent_instruction

def test_tokenize():
    text = "A e o de gato cachorro the and running"
    tokens = _tokenize(text)
    assert "gato" in tokens
    assert "cachorro" in tokens
    assert "running" in tokens
    assert "de" not in tokens
    assert "the" not in tokens

def test_compute_tf():
    tokens = ["gato", "gato", "cachorro"]
    tf = _compute_tf(tokens)
    assert tf["gato"] == 2 / 3
    assert tf["cachorro"] == 1 / 3

def test_compute_idf():
    docs = [
        ["gato", "cachorro"],
        ["gato", "passaro"],
        ["peixe"]
    ]
    idf = _compute_idf(docs)
    import math
    assert math.isclose(idf["gato"], math.log(4 / 3) + 1)
    assert math.isclose(idf["peixe"], math.log(2) + 1)

def test_cosine_similarity():
    vec_a = {"gato": 1.0, "cachorro": 2.0}
    vec_b = {"gato": 2.0, "peixe": 3.0}
    import math
    expected = 2.0 / (math.sqrt(5) * math.sqrt(13))
    assert math.isclose(_cosine_similarity(vec_a, vec_b), expected)

    assert _cosine_similarity({"gato": 1.0}, {"peixe": 1.0}) == 0.0
    assert _cosine_similarity({"gato": 0.0}, {"peixe": 1.0}) == 0.0

def test_hash_instruction():
    text = "   This is a test instruction.   "
    h1 = hash_instruction(text)
    h2 = hash_instruction("This is a test instruction.")
    assert h1 == h2
    assert len(h1) == 16

def test_experience_store_lifecycle(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.experience_store_sqlite.DB_PATH", db_path):
        store = SqliteExperienceStore(gamma=0.9, max_experiences=3)

        # Test initial state
        assert len(store.experiences) == 0

        exp1 = Experience("h1", "strat1", 0.1, 1.1, "feedback one", timestamp=time.time())
        exp2 = Experience("h2", "strat2", 0.2, 1.2, "feedback two", timestamp=time.time())
        exp3 = Experience("h3", "strat1", 0.3, 1.3, "feedback three", timestamp=time.time())
        exp4 = Experience("h4", "strat3", 0.4, 1.4, "feedback four", timestamp=time.time())

        store.add(exp1)
        store.add(exp2)
        store.add(exp3)
        assert len(store.experiences) == 3

        # Adding exp4 should truncate the oldest one (exp1) because max_experiences=3
        store.add(exp4)
        assert len(store.experiences) == 3
        # SQLite returns newest first (ORDER BY timestamp DESC): [h4, h3, h2]
        assert store.experiences[0].skill_hash == "h4"
        assert store.experiences[2].skill_hash == "h2"

        # Save to disk
        store.save()
        store.close()

        # Load from disk in a new store
        store2 = SqliteExperienceStore(gamma=0.9, max_experiences=3)
        assert len(store2.experiences) == 3
        assert store2.experiences[0].skill_hash == "h4"
        assert store2.experiences[2].skill_hash == "h2"
        store2.close()

def test_experience_store_query_similar(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.experience_store_sqlite.DB_PATH", db_path):
        store = SqliteExperienceStore(gamma=0.9, max_experiences=10)

        now = time.time()
        exp_recent = Experience("h1", "s1", 0.5, 1.5, "gato feliz deitado no sol", timestamp=now)
        exp_old = Experience("h2", "s2", 0.5, 1.5, "gato feliz deitado no sol", timestamp=now - 86400 * 5)

        store.add(exp_old)
        store.add(exp_recent)

        results = store.query_similar("gato", top_k=2)
        assert len(results) == 2
        # Since text is identical, the decay factor makes recent have higher score
        assert results[0].skill_hash == "h1"
        assert results[1].skill_hash == "h2"
        store.close()

def test_experience_store_strategy_stats(tmp_path):
    db_path = tmp_path / "test.db"
    with patch("src.experience_store_sqlite.DB_PATH", db_path):
        store = SqliteExperienceStore()

        exp1 = Experience("h1", "strat1", 0.2, 1.0, "f1")
        exp2 = Experience("h2", "strat1", 0.4, 2.0, "f2")
        exp3 = Experience("h3", "strat2", 0.3, 1.5, "f3")

        store.add(exp1)
        store.add(exp2)
        store.add(exp3)

        stats = store.get_strategy_stats()

        assert "strat1" in stats
        assert stats["strat1"]["count"] == 2
        assert pytest.approx(stats["strat1"]["total_delta"]) == 0.6
        assert pytest.approx(stats["strat1"]["mean_delta"]) == 0.3
        assert pytest.approx(stats["strat1"]["total_reward"]) == 3.0

        assert "strat2" in stats
        assert stats["strat2"]["count"] == 1
        assert pytest.approx(stats["strat2"]["total_delta"]) == 0.3
        assert pytest.approx(stats["strat2"]["mean_delta"]) == 0.3
        assert pytest.approx(stats["strat2"]["total_reward"]) == 1.5
        store.close()
