#!/usr/bin/env python3
"""Bounded synthetic null pilot, not candidate certification or market evidence."""
import json
import math
import random

from swarm_worker.scientific_bootstrap import paired_bootstrap


def main():
    results = []
    for rho in (0, .6):
        counts = dict(valid=0, invalid=0, primary_rejections=0, advantage_rejections=0,
                      primary_coverage=0, advantage_coverage=0)
        for trial in range(100):
            rng = random.Random(17000 + trial)
            y, state = [], 0
            for _ in range(850):
                state = rho*state + math.sqrt(1-rho*rho)*rng.gauss(0, 1)
                y.append(state)
            primary_events = [rng.random() < .05 for _ in y]
            rival_events = [rng.random() < .05 for _ in y]
            result = paired_bootstrap(y, y, primary_events, rival_events,
                                      block_length=24, replicates=199, seed=trial)
            if result['status'] != 'ok':
                counts['invalid'] += 1
                continue
            counts['valid'] += 1
            for prefix, statistic in zip(('primary', 'advantage'), result['statistics']):
                counts[prefix+'_rejections'] += int(
                    statistic['centered_p'] <= .05 and statistic['observed'] > 0)
                counts[prefix+'_coverage'] += int(
                    statistic['interval95'][0] <= 0 <= statistic['interval95'][1])
        results.append({'rho': rho, **counts})
    print(json.dumps({'synthetic_only': True, 'pilot_not_certification': True,
                      'outer_replicates': 100, 'inner_replicates': 199,
                      'results': results}, indent=2))


if __name__ == '__main__':
    main()
