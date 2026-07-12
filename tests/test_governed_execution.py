from src.domain.governed_execution import (
    CandidateScore,
    DecisionStatus,
    ExecutionBudget,
    ExecutionStatus,
    InMemoryExecutionRepository,
    OptimizationCandidate,
    OptimizationExecutionService,
    ThresholdQualityPolicy,
)


def build_service(minimum_score: float = 0.8):
    return OptimizationExecutionService(
        InMemoryExecutionRepository(),
        ThresholdQualityPolicy(minimum_score),
    )


def build_candidate(
    iteration: int = 1,
    score: float = 0.9,
    blocking_rule_passed: bool = True,
) -> OptimizationCandidate:
    return OptimizationCandidate(
        candidate_id="candidate-1",
        content="---\nname: optimized\n---",
        source="mcts",
        iteration=iteration,
        scores=(
            CandidateScore(
                evaluator_name="semantic",
                evaluator_version="1.0",
                score=score,
                blocking_rule_passed=blocking_rule_passed,
            ),
        ),
    )


def test_approved_candidate_closes_execution_as_approved():
    service = build_service()
    execution = service.start("---\nname: original\n---", ExecutionBudget(3, 60))

    decision = service.evaluate_candidate(execution.execution_id, build_candidate(), 0.8)

    assert decision.status == DecisionStatus.APPROVED
    assert service._repository.get(execution.execution_id).status == ExecutionStatus.APPROVED


def test_blocking_rule_failure_rejects_high_scoring_candidate():
    service = build_service()
    execution = service.start("original", ExecutionBudget(3, 60))

    decision = service.evaluate_candidate(
        execution.execution_id,
        build_candidate(score=1.0, blocking_rule_passed=False),
        0.8,
    )

    assert decision.status == DecisionStatus.REJECTED
    assert any(not item.passed and item.rule_id == "RN-05" for item in decision.evidence)


def test_regression_rejects_candidate_even_when_above_threshold():
    service = build_service(0.8)
    execution = service.start("original", ExecutionBudget(3, 60))

    decision = service.evaluate_candidate(execution.execution_id, build_candidate(score=0.85), 0.9)

    assert decision.status == DecisionStatus.REJECTED
    assert any(not item.passed and item.rule_id == "RN-07" for item in decision.evidence)


def test_attempt_budget_rejects_candidate_and_records_limit():
    service = build_service()
    execution = service.start("original", ExecutionBudget(1, 60))

    decision = service.evaluate_candidate(execution.execution_id, build_candidate(iteration=2), 0.8)

    assert decision.status == DecisionStatus.REJECTED
    assert decision.evidence[0].details["limit"] == "maximum_attempts"


def test_terminal_execution_cannot_be_cancelled():
    service = build_service()
    execution = service.start("original", ExecutionBudget(3, 60))
    service.evaluate_candidate(execution.execution_id, build_candidate(), 0.8)

    try:
        service.cancel(execution.execution_id)
    except ValueError as error:
        assert str(error) == "execution is not running"
    else:
        raise AssertionError("terminal execution must reject cancellation")


def test_empty_original_content_is_rejected_before_execution_starts():
    service = build_service()

    try:
        service.start("   ", ExecutionBudget(3, 60))
    except ValueError as error:
        assert str(error) == "original_content must not be empty"
    else:
        raise AssertionError("empty content must be rejected")
