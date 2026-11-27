"""Versioned read-only capabilities for bounded method investigation."""
from copy import deepcopy

TOOLS = {
    'inspect_native_source': {
        'description': 'Read a complete Python file from the immutable native source commit, at most 64 KiB. No working-tree files or commands.',
        'arguments': {'path': 'src/bt/, scripts/, or tests/ Python path; no traversal'}},
    'read_evidence': {
        'description': 'Read a retained evidence document by exact digest.',
        'arguments': {'digest': 'retained SHA-256 digest'}},
    'inspect_contract': {
        'description': 'Inspect frozen requirements, source and permitted repair scope.',
        'arguments': {}},
    'reproduce_diagnostic': {
        'description': 'Run the exact approved native diagnostic on the current proposal, not a shell command.',
        'arguments': {}},
}


def catalog(names):
    if not set(names) <= set(TOOLS):
        raise ValueError('Unknown investigation tool; explicit adapter commissioning required')
    return {key: deepcopy(TOOLS[key]) for key in names}

