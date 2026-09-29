from swarm_worker.research_utilization import (
    ResourceSnapshot,
    UtilizationPolicy,
    WorkItem,
    WorkKind,
    plan_research_utilization,
)


def item(name: str, kind: WorkKind, **changes: bool) -> WorkItem:
    values = {"execution_authorized": True, **changes}
    return WorkItem(name, kind, **values)


def test_current_vm_capacity_runs_two_backtests_without_ram_overcommit() -> None:
    plan = plan_research_utilization(
        ResourceSnapshot(cpu_count=36, available_ram_gib=66),
        [
            item("bt-1", WorkKind.APPROVED_BACKTEST),
            item("bt-2", WorkKind.APPROVED_BACKTEST),
        ],
    )

    assert plan.worker_budget == 12
    assert [allocation.workers for allocation in plan.allocations] == [6, 6]
    assert plan.state == "backtests_running"


def test_three_full_eight_worker_backtests_require_measured_capacity() -> None:
    policy = UtilizationPolicy(target_workers=24)
    plan = plan_research_utilization(
        ResourceSnapshot(cpu_count=36, available_ram_gib=120),
        [
            item("bt-1", WorkKind.APPROVED_BACKTEST),
            item("bt-2", WorkKind.APPROVED_BACKTEST),
            item("bt-3", WorkKind.APPROVED_BACKTEST),
        ],
        policy,
    )

    assert plan.worker_budget == 24
    assert [allocation.workers for allocation in plan.allocations] == [8, 8, 8]


def test_third_backtest_waits_until_each_job_can_receive_six_workers() -> None:
    jobs = [
        item("bt-1", WorkKind.APPROVED_BACKTEST),
        item("bt-2", WorkKind.APPROVED_BACKTEST),
        item("bt-3", WorkKind.APPROVED_BACKTEST),
    ]

    constrained = plan_research_utilization(
        ResourceSnapshot(cpu_count=36, available_ram_gib=66), jobs
    )
    expanded = plan_research_utilization(
        ResourceSnapshot(cpu_count=36, available_ram_gib=90),
        jobs,
        UtilizationPolicy(target_workers=18),
    )

    assert [allocation.workers for allocation in constrained.allocations] == [6, 6]
    assert [allocation.workers for allocation in expanded.allocations] == [6, 6, 6]


def test_signal_screen_is_productive_fallback_when_backtest_queue_is_empty() -> None:
    plan = plan_research_utilization(
        ResourceSnapshot(cpu_count=16, available_ram_gib=40),
        [
            item("screen-1", WorkKind.SIGNAL_SCREEN),
            item("representation-1", WorkKind.REPRESENTATION_AUDIT),
        ],
    )

    assert plan.state == "fallback_research_running"
    assert [allocation.kind for allocation in plan.allocations] == [
        WorkKind.SIGNAL_SCREEN,
        WorkKind.REPRESENTATION_AUDIT,
    ]


def test_policy_never_uses_unapproved_code_capital_or_sealed_oos() -> None:
    plan = plan_research_utilization(
        ResourceSnapshot(cpu_count=36, available_ram_gib=66),
        [
            item("unapproved", WorkKind.APPROVED_BACKTEST, execution_authorized=False),
            item("new-code", WorkKind.SIGNAL_SCREEN, requires_new_code=True),
            item("oos", WorkKind.SIGNAL_SCREEN, opens_sealed_oos=True),
            item("capital", WorkKind.APPROVED_BACKTEST, capital_or_order_authority=True),
        ],
    )

    assert plan.allocations == ()
    assert plan.state == "eligible_queue_empty"
    assert dict(plan.rejected) == {
        "capital": "capital_or_order_authority_forbidden",
        "new-code": "new_code_requires_explicit_approval",
        "oos": "sealed_oos_cannot_be_used_for_research_selection",
        "unapproved": "execution_not_authorized",
    }


def test_resource_pressure_is_explicit_not_reported_as_idle() -> None:
    plan = plan_research_utilization(
        ResourceSnapshot(cpu_count=36, available_ram_gib=11),
        [item("bt-1", WorkKind.APPROVED_BACKTEST)],
    )

    assert plan.worker_budget == 0
    assert plan.state == "resource_blocked"
