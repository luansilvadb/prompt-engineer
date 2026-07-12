from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from time import monotonic
from typing import Mapping, Protocol, Sequence
from uuid import uuid4


class ExecutionStatus(str, Enum):
    RECEIVED = "received"
    RUNNING = "running"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True)
class ExecutionBudget:
    maximum_attempts: int
    maximum_duration_seconds: float
    maximum_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be at least one")
        if self.maximum_duration_seconds <= 0:
            raise ValueError("maximum_duration_seconds must be positive")
        if self.maximum_tokens is not None and self.maximum_tokens < 1:
            raise ValueError("maximum_tokens must be positive when provided")


@dataclass(frozen=True)
class CandidateScore:
    evaluator_name: str
    evaluator_version: str
    score: float
    blocking_rule_passed: bool
    details: Mapping[str, float | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class OptimizationCandidate:
    candidate_id: str
    content: str
    source: str
    iteration: int
    scores: Sequence[CandidateScore] = field(default_factory=tuple)


@dataclass(frozen=True)
class DecisionEvidence:
    evidence_id: str
    rule_id: str
    passed: bool
    severity: str
    recorded_at: datetime
    details: Mapping[str, float | str | bool] = field(default_factory=dict)


@dataclass(frozen=True)
class QualityDecision:
    decision_id: str
    execution_id: str
    candidate_id: str
    status: DecisionStatus
    aggregate_score: float
    baseline_score: float
    evidence: Sequence[DecisionEvidence]


@dataclass(frozen=True)
class ExecutionSnapshot:
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    finished_at: datetime | None
    budget: ExecutionBudget
    decision: QualityDecision | None


class CandidateEvaluator(Protocol):
    def evaluate(
        self,
        execution_id: str,
        candidate: OptimizationCandidate,
        original_content: str,
    ) -> CandidateScore: ...


class QualityPolicy(Protocol):
    def decide(
        self,
        execution_id: str,
        candidate: OptimizationCandidate,
        baseline_score: float,
    ) -> QualityDecision: ...


class ExecutionRepository(Protocol):
    def create(self, snapshot: ExecutionSnapshot) -> None: ...

    def append_evidence(
        self,
        execution_id: str,
        evidence: Sequence[DecisionEvidence],
    ) -> None: ...

    def transition(
        self,
        execution_id: str,
        expected_status: ExecutionStatus,
        next_status: ExecutionStatus,
        decision: QualityDecision | None,
    ) -> ExecutionSnapshot: ...

    def get(self, execution_id: str) -> ExecutionSnapshot | None: ...


class InMemoryExecutionRepository:
    def __init__(self) -> None:
        self._snapshots: dict[str, ExecutionSnapshot] = {}
        self._evidence: dict[str, list[DecisionEvidence]] = {}
        self._lock = Lock()

    def create(self, snapshot: ExecutionSnapshot) -> None:
        with self._lock:
            if snapshot.execution_id in self._snapshots:
                raise ValueError("execution already exists")
            self._snapshots[snapshot.execution_id] = snapshot
            self._evidence[snapshot.execution_id] = []

    def append_evidence(self, execution_id: str, evidence: Sequence[DecisionEvidence]) -> None:
        with self._lock:
            if execution_id not in self._snapshots:
                raise KeyError("execution not found")
            self._evidence[execution_id].extend(evidence)

    def transition(
        self,
        execution_id: str,
        expected_status: ExecutionStatus,
        next_status: ExecutionStatus,
        decision: QualityDecision | None,
    ) -> ExecutionSnapshot:
        with self._lock:
            snapshot = self._get_required(execution_id)
            if snapshot.status != expected_status:
                raise ValueError("unexpected execution status")
            if snapshot.status in _TERMINAL_STATUSES:
                raise ValueError("terminal executions cannot transition")
            finished_at = _now() if next_status in _TERMINAL_STATUSES else None
            updated = ExecutionSnapshot(
                execution_id=snapshot.execution_id,
                status=next_status,
                started_at=snapshot.started_at,
                finished_at=finished_at,
                budget=snapshot.budget,
                decision=decision,
            )
            self._snapshots[execution_id] = updated
            return updated

    def get(self, execution_id: str) -> ExecutionSnapshot | None:
        with self._lock:
            return self._snapshots.get(execution_id)

    def _get_required(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = self._snapshots.get(execution_id)
        if snapshot is None:
            raise KeyError("execution not found")
        return snapshot


class ThresholdQualityPolicy:
    def __init__(self, minimum_score: float) -> None:
        self._minimum_score = minimum_score

    def decide(
        self,
        execution_id: str,
        candidate: OptimizationCandidate,
        baseline_score: float,
    ) -> QualityDecision:
        scores = tuple(candidate.scores)
        aggregate_score = _aggregate_score(scores)
        evidence = _build_evidence(scores, aggregate_score, baseline_score)
        is_approved = (
            bool(scores)
            and all(score.blocking_rule_passed for score in scores)
            and aggregate_score >= self._minimum_score
            and aggregate_score >= baseline_score
        )
        return QualityDecision(
            decision_id=str(uuid4()),
            execution_id=execution_id,
            candidate_id=candidate.candidate_id,
            status=DecisionStatus.APPROVED if is_approved else DecisionStatus.REJECTED,
            aggregate_score=aggregate_score,
            baseline_score=baseline_score,
            evidence=evidence,
        )


class OptimizationExecutionService:
    def __init__(self, repository: ExecutionRepository, policy: QualityPolicy) -> None:
        self._repository = repository
        self._policy = policy
        self._started_at: dict[str, float] = {}

    def start(self, original_content: str, budget: ExecutionBudget) -> ExecutionSnapshot:
        if not original_content.strip():
            raise ValueError("original_content must not be empty")
        execution_id = str(uuid4())
        snapshot = ExecutionSnapshot(
            execution_id=execution_id,
            status=ExecutionStatus.RECEIVED,
            started_at=_now(),
            finished_at=None,
            budget=budget,
            decision=None,
        )
        self._repository.create(snapshot)
        self._started_at[execution_id] = monotonic()
        return self._repository.transition(
            execution_id,
            ExecutionStatus.RECEIVED,
            ExecutionStatus.RUNNING,
            None,
        )

    def evaluate_candidate(
        self,
        execution_id: str,
        candidate: OptimizationCandidate,
        baseline_score: float,
    ) -> QualityDecision:
        snapshot = self._get_running(execution_id)
        if candidate.iteration > snapshot.budget.maximum_attempts:
            return self._reject_for_budget(execution_id, candidate, baseline_score, "maximum_attempts")
        if monotonic() - self._started_at[execution_id] > snapshot.budget.maximum_duration_seconds:
            return self._reject_for_budget(execution_id, candidate, baseline_score, "maximum_duration_seconds")
        decision = self._policy.decide(execution_id, candidate, baseline_score)
        self._repository.append_evidence(execution_id, decision.evidence)
        next_status = ExecutionStatus.APPROVED if decision.status == DecisionStatus.APPROVED else ExecutionStatus.REJECTED
        self._repository.transition(execution_id, ExecutionStatus.RUNNING, next_status, decision)
        return decision

    def cancel(self, execution_id: str) -> ExecutionSnapshot:
        self._get_running(execution_id)
        return self._repository.transition(
            execution_id,
            ExecutionStatus.RUNNING,
            ExecutionStatus.CANCELLED,
            None,
        )

    def _get_running(self, execution_id: str) -> ExecutionSnapshot:
        snapshot = self._repository.get(execution_id)
        if snapshot is None:
            raise KeyError("execution not found")
        if snapshot.status != ExecutionStatus.RUNNING:
            raise ValueError("execution is not running")
        return snapshot

    def _reject_for_budget(
        self,
        execution_id: str,
        candidate: OptimizationCandidate,
        baseline_score: float,
        limit_name: str,
    ) -> QualityDecision:
        evidence = DecisionEvidence(
            evidence_id=str(uuid4()),
            rule_id="RN-03",
            passed=False,
            severity="blocking",
            recorded_at=_now(),
            details={"limit": limit_name},
        )
        decision = QualityDecision(
            decision_id=str(uuid4()),
            execution_id=execution_id,
            candidate_id=candidate.candidate_id,
            status=DecisionStatus.REJECTED,
            aggregate_score=0.0,
            baseline_score=baseline_score,
            evidence=(evidence,),
        )
        self._repository.append_evidence(execution_id, decision.evidence)
        self._repository.transition(execution_id, ExecutionStatus.RUNNING, ExecutionStatus.REJECTED, decision)
        return decision


_TERMINAL_STATUSES = frozenset({
    ExecutionStatus.APPROVED,
    ExecutionStatus.REJECTED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
})


def _aggregate_score(scores: Sequence[CandidateScore]) -> float:
    if not scores:
        return 0.0
    return sum(score.score for score in scores) / len(scores)


def _build_evidence(
    scores: Sequence[CandidateScore],
    aggregate_score: float,
    baseline_score: float,
) -> tuple[DecisionEvidence, ...]:
    score_evidence = tuple(
        DecisionEvidence(
            evidence_id=str(uuid4()),
            rule_id="RN-05",
            passed=score.blocking_rule_passed,
            severity="blocking",
            recorded_at=_now(),
            details={"evaluator": score.evaluator_name, "score": score.score},
        )
        for score in scores
    )
    comparison = DecisionEvidence(
        evidence_id=str(uuid4()),
        rule_id="RN-07",
        passed=aggregate_score >= baseline_score,
        severity="blocking",
        recorded_at=_now(),
        details={"aggregate_score": aggregate_score, "baseline_score": baseline_score},
    )
    return score_evidence + (comparison,)


def _now() -> datetime:
    return datetime.now(timezone.utc)
