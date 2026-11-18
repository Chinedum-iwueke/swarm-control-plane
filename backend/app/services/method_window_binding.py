"""Prepare a coverage-only successor for explicit approval, never execution."""
from copy import deepcopy
from datetime import datetime

from app.services.graph import digest_document as digest


def prepare_window_binding(proposal, report, *, source_commit, envelope_start, envelope_end):
    """Caller verifies native receipt custody before registering this evidence.

    No dates are inferred from outcomes. This projection leaves the retained
    proposal intact and requires its own inclusion in an approved successor.
    """
    def clock(value):
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('Timezone-aware window required')
        return dt.timestamp()

    if (report.get('status') != 'ready' or report.get('source_commit') != source_commit
            or report.get('execution_authority') is not False):
        raise ValueError('Ready same-source no-execution native report required')
    minima = proposal['support_minima']
    step = minima['research_bar_minutes'] * 60
    if type(step) is not int or step <= 0:
        raise ValueError('Positive integral research clock required')
    lower, upper = clock(envelope_start), clock(envelope_end)
    plans = report['validation_plans']
    if set(plans) != {'smoke', 'scientific'}:
        raise ValueError('Both native validation modes required')
    modes = {}
    for mode, plan in plans.items():
        if (plan.get('status') != 'ready' or plan.get('reasons') or plan.get('mode') != mode
                or plan.get('source_commit') != source_commit
                or not plan.get('coverage_receipt_digests')
                or plan.get('plan_digest') != digest({k: v for k, v in plan.items() if k != 'plan_digest'})):
            raise ValueError('Native plan binding invalid')
        names = ['training', 'validation', 'test'] if mode == 'scientific' else ['smoke']
        parts = plan['partitions']
        if set(parts) != set(names + ['feature_warmup', 'target_tail']):
            raise ValueError('Unexpected native partition topology')
        spans = {k: (clock(v['start']), clock(v['end'])) for k, v in parts.items()}
        for start, end in spans.values():
            if not lower <= start < end <= upper or start % step or end % step:
                raise ValueError('Partition outside envelope or research clock')
        warm, tail = spans['feature_warmup'], spans['target_tail']
        if (warm[1] != spans[names[0]][0] or tail[0] != spans[names[-1]][1]
                or (warm[1]-warm[0])/step < minima['feature_warmup_bars']
                or (tail[1]-tail[0])/step != minima['target_horizon_bars']):
            raise ValueError('Warmup or target-only tail mismatch')
        gap = max(minima['purge_bars'], minima['target_horizon_bars']) + minima['embargo_bars']
        for left, right in zip(names, names[1:]):
            if (spans[right][0]-spans[left][1])/step < gap:
                raise ValueError('Insufficient boundary exclusions')
        for name in names:
            minimum = minima['smoke_bars'] if mode == 'smoke' else minima['minimum_'+name+'_bars']
            if (spans[name][1]-spans[name][0])/step < minimum:
                raise ValueError('Partition capacity below frozen minimum')
        if mode == 'scientific' and (tail[1]-spans[names[0]][0])/86400 < minima['minimum_scientific_window_days']:
            raise ValueError('Scientific duration below frozen minimum')
        modes[mode] = dict(plan_digest=plan['plan_digest'], partitions=deepcopy(parts),
            calendar_capacity_bars={n: int((spans[n][1]-spans[n][0])/step) for n in names},
            eligible_rows_observed=False, target_tail_may_generate_decisions=False)
    return dict(schema_version='method-coverage-window-successor-v1',
        parent_proposal_digest=digest(proposal), scientific_identity_digest=digest(proposal['scientific_identity']),
        support_minima_digest=digest(minima), native_report_digest=digest(report),
        source_commit=source_commit, modes=modes,
        selection_basis='coverage_only', historical_proposal_unchanged=True,
        requires_exact_successor_approval=True, scientific_approval=False, execution_authority=False)
