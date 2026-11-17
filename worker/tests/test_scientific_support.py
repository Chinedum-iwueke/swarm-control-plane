import math

import pytest

from swarm_worker.scientific_support import event_floor_probability, joint_gate_bounds


@pytest.mark.parametrize("rows,p,floor", [(10, .5, 5), (20, .1, 3), (30, .9, 26)])
def test_matches_direct_binomial_sum(rows, p, floor):
    expected = sum(math.comb(rows, k) * p**k * (1-p)**(rows-k)
                   for k in range(floor, rows+1))
    assert event_floor_probability(rows=rows, floor=floor, event_probability=p) == pytest.approx(expected)


def test_boundaries_and_monotonicity():
    assert event_floor_probability(rows=10, floor=0, event_probability=0) == 1
    assert event_floor_probability(rows=10, floor=11, event_probability=1) == 0
    assert event_floor_probability(rows=10, floor=10, event_probability=1) == 1
    assert event_floor_probability(rows=10, floor=1, event_probability=0) == 0
    lower = event_floor_probability(rows=850, floor=40, event_probability=.05)
    assert .6 < lower < .75
    assert lower < event_floor_probability(rows=850, floor=40, event_probability=.1)
    assert lower > event_floor_probability(rows=850, floor=40, event_probability=.045)


def test_tiny_tail_is_not_lost_to_complement_rounding():
    assert event_floor_probability(rows=100, floor=100, event_probability=.5) == pytest.approx(.5**100, rel=1e-10, abs=0)


def test_bounds_do_not_assume_independence():
    assert joint_gate_bounds([.7, .7]) == pytest.approx({"lower": .4, "upper": .7})
    assert joint_gate_bounds([.7] * 8) == {"lower": 0, "upper": .7}


@pytest.mark.parametrize("changes", [{"rows": 100001}, {"rows": True}, {"floor": -1},
                                    {"event_probability": float("nan")}, {"event_probability": 1.1}])
def test_rejects_invalid_and_unbounded_inputs(changes):
    args = dict(rows=850, floor=40, event_probability=.05)
    args.update(changes)
    with pytest.raises(ValueError):
        event_floor_probability(**args)


@pytest.mark.parametrize("values", [[], [float("nan")], [1.1], [.5] * 101])
def test_rejects_invalid_joint_gates(values):
    with pytest.raises(ValueError):
        joint_gate_bounds(values)
