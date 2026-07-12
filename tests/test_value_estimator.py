import math
import pytest
from src.value_estimator import _extract_features, ValueEstimator

def test_extract_features_empty():
    features = _extract_features("")
    assert isinstance(features, dict)
    assert "length" in features
    assert "structure" in features
    assert "format" in features
    assert "robustness" in features
    assert "diversity" in features
    assert "completeness" in features
    # An empty text should have 0.0 completeness, structures, format
    assert features["completeness"] == 0.0
    assert features["structure"] == 0.0
    assert features["format"] == 0.0

def test_extract_features_sweet_spot_length():
    # Sweet spot is 3000 chars. Length score should be 1.0.
    text = "x" * 3000
    features = _extract_features(text)
    assert pytest.approx(features["length"]) == 1.0

def test_extract_features_very_short():
    # Very short should have lower length score
    features_short = _extract_features("short")
    # 500 is min clamp. 1.0 - abs(500 - 3000)/3000 = 1.0 - 2500/3000 = 1.0 - 0.833 = 0.166
    assert features_short["length"] < 0.2

def test_extract_features_rich_formatting():
    rich_text = """# Header 1
## Header 2
This is some **bold text**.
- List item 1
- List item 2
```python
print("Hello")
```
This is a detailed example.
Never do anti-patterns.
"""
    features = _extract_features(rich_text)
    # Check that it extracted completeness features (has examples, has antipatterns)
    assert features["completeness"] == 1.0
    assert features["structure"] > 0.0
    assert features["format"] > 0.0

def test_value_estimator_initial_state():
    estimator = ValueEstimator(learning_rate=0.2)
    assert estimator.learning_rate == 0.2
    assert estimator._bias == 0.3
    assert estimator._n_updates == 0
    assert estimator.confidence == 0.0

def test_value_estimator_estimate_bounds():
    estimator = ValueEstimator()
    # Estimate should always return a float between 0.0 and 1.0
    text = "Some random instruction text."
    val = estimator.estimate(text)
    assert 0.0 <= val <= 1.0

def test_value_estimator_update_convergence():
    estimator = ValueEstimator(learning_rate=0.5)
    text = "## Header\n**Bold** instruction with SEMPRE and example and avoid antipattern."

    initial_est = estimator.estimate(text)

    # Update with actual reward = 0.9 (assuming initial_est is lower)
    # Perform multiple updates
    for _ in range(5):
        estimator.update(text, 0.9)

    final_est = estimator.estimate(text)

    # Since actual_reward (0.9) is likely higher than the initial_est (~0.3-0.5),
    # the estimator should move closer to 0.9
    if initial_est < 0.9:
        assert final_est > initial_est
    elif initial_est > 0.9:
        assert final_est < initial_est

    assert estimator._n_updates == 5
    assert estimator.confidence > 0.0

def test_value_estimator_confidence_progression():
    estimator = ValueEstimator()
    assert estimator.confidence == 0.0

    # After 1 update
    estimator.update("test text", 0.8)
    conf_1 = estimator.confidence
    assert conf_1 == min(1.0, math.log(2) / math.log(20))

    # After 20 updates, it should reach 1.0 because log(21)/log(20) > 1.0, clamped at 1.0
    for _ in range(20):
        estimator.update("test text", 0.8)

    assert estimator.confidence == 1.0
