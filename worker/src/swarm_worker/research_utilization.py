from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import floor


class WorkKind(StrEnum):
    APPROVED_BACKTEST = "approved_backtest"
    SIGNAL_SCREEN = "native_signal_screen"
    REPRESENTATION_AUDIT = "representation_audit"
    EXTERNAL_EVIDENCE = "external_evidence_ingestion"
    SKILL_REPLAY = "held_out_skill_replay"


_PRIORITY = {
    WorkKind.APPROVED_BACKTEST: 0,
    WorkKind.SIGNAL_SCREEN: 1,
    WorkKind.REPRESENTATION_AUDIT: 2,
    WorkKind.EXTERNAL_EVIDENCE: 3,
    WorkKind.SKILL_REPLAY: 4,
}


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_count: int
    available_ram_gib: float


@dataclass(frozen=True)
class UtilizationPolicy:
    target_workers: int = 16
    max_workers_per_job: int = 8
    max_concurrent_jobs: int = 3
    target_concurrent_backtests: int = 2
    burst_concurrent_backtests: int = 3
    minimum_workers_per_backtest: int = 4
    minimum_workers_per_burst_backtest: int = 6
    estimated_worker_ram_gib: float = 4.5
    minimum_free_ram_gib: float = 8.0
    reserved_cpus: int = 2


@dataclass(frozen=True)
class WorkItem:
    work_id: str
    kind: WorkKind
    execution_authorized: bool
    requires_new_code: bool = False
    opens_sealed_oos: bool = False
    capital_or_order_authority: bool = False


@dataclass(frozen=True)
class Allocation:
    work_id: str
    kind: WorkKind
    workers: int


@dataclass(frozen=True)
class UtilizationPlan:
    worker_budget: int
    allocations: tuple[Allocation, ...]
    rejected: tuple[tuple[str, str], ...]
    state: str


def plan_research_utilization(
    resources: ResourceSnapshot,
    items: list[WorkItem],
    policy: UtilizationPolicy | None = None,
) -> UtilizationPlan:
    """Allocate bounded research work without expanding scientific authority."""
    policy = policy or UtilizationPolicy()
    worker_budget = _worker_budget(resources, policy)
    rejected: list[tuple[str, str]] = []
    eligible: list[WorkItem] = []
    for item in sorted(items, key=lambda value: (_PRIORITY[value.kind], value.work_id)):
        reason = _rejection_reason(item)
        if reason is None:
            eligible.append(item)
        else:
            rejected.append((item.work_id, reason))

    if worker_budget <= 0:
        return UtilizationPlan(
            worker_budget=0,
            allocations=(),
            rejected=tuple(rejected),
            state="resource_blocked",
        )

    backtests = [
        item for item in eligible if item.kind == WorkKind.APPROVED_BACKTEST
    ]
    if backtests:
        allocations = _allocate_backtests(backtests, worker_budget, policy)
        if allocations:
            return UtilizationPlan(
                worker_budget=worker_budget,
                allocations=allocations,
                rejected=tuple(rejected),
                state="backtests_running",
            )

    fallbacks = [
        item for item in eligible if item.kind != WorkKind.APPROVED_BACKTEST
    ]
    allocations = _allocate_fallbacks(fallbacks, worker_budget, policy)
    return UtilizationPlan(
        worker_budget=worker_budget,
        allocations=allocations,
        rejected=tuple(rejected),
        state="fallback_research_running" if allocations else "eligible_queue_empty",
    )


def _worker_budget(
    resources: ResourceSnapshot, policy: UtilizationPolicy
) -> int:
    if resources.cpu_count <= policy.reserved_cpus:
        return 0
    usable_ram = resources.available_ram_gib - policy.minimum_free_ram_gib
    if usable_ram < policy.estimated_worker_ram_gib:
        return 0
    memory_workers = floor(usable_ram / policy.estimated_worker_ram_gib)
    cpu_workers = resources.cpu_count - policy.reserved_cpus
    return max(0, min(policy.target_workers, memory_workers, cpu_workers))


def _rejection_reason(item: WorkItem) -> str | None:
    if item.capital_or_order_authority:
        return "capital_or_order_authority_forbidden"
    if item.requires_new_code:
        return "new_code_requires_explicit_approval"
    if item.opens_sealed_oos:
        return "sealed_oos_cannot_be_used_for_research_selection"
    if not item.execution_authorized:
        return "execution_not_authorized"
    return None


def _allocate_backtests(
    items: list[WorkItem], worker_budget: int, policy: UtilizationPolicy
) -> tuple[Allocation, ...]:
    max_by_minimum = worker_budget // policy.minimum_workers_per_backtest
    if max_by_minimum <= 0:
        return ()
    target = min(
        len(items),
        policy.target_concurrent_backtests,
        policy.max_concurrent_jobs,
        max_by_minimum,
    )
    burst_workers = (
        policy.burst_concurrent_backtests
        * policy.minimum_workers_per_burst_backtest
    )
    if (
        len(items) >= policy.burst_concurrent_backtests
        and policy.max_concurrent_jobs >= policy.burst_concurrent_backtests
        and worker_budget >= burst_workers
    ):
        target = policy.burst_concurrent_backtests
    return _fair_allocations(items[:target], worker_budget, policy.max_workers_per_job)


def _allocate_fallbacks(
    items: list[WorkItem], worker_budget: int, policy: UtilizationPolicy
) -> tuple[Allocation, ...]:
    if not items:
        return ()
    selected = items[: policy.max_concurrent_jobs]
    return _fair_allocations(selected, worker_budget, policy.max_workers_per_job)


def _fair_allocations(
    items: list[WorkItem], worker_budget: int, max_workers_per_job: int
) -> tuple[Allocation, ...]:
    count = len(items)
    if count == 0:
        return ()
    base = min(max_workers_per_job, worker_budget // count)
    remainder = worker_budget - (base * count)
    allocations: list[Allocation] = []
    for item in items:
        workers = base
        if remainder > 0 and workers < max_workers_per_job:
            workers += 1
            remainder -= 1
        allocations.append(Allocation(item.work_id, item.kind, workers))
    return tuple(allocation for allocation in allocations if allocation.workers > 0)
