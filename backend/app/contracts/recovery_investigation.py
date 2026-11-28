"""Versioned read-only capabilities for bounded method investigation."""
from copy import deepcopy

TOOLS = {
    'search_evidence': {
        'description': 'Search canonical evidence within the exact task retrieval scope. Results retain provenance and are not scientific approval.',
        'arguments': {'query': '2 to 1000 characters; no model-selected project or access scope'}},
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


def diagnostic_catalog(initial, state, tools, digest):
    """Admit recorded tool observations, never arbitrary author output."""
    catalog(tools)
    result = deepcopy(initial)
    if any(digest(value) != key for key, value in result.items()):
        raise ValueError('Initial investigation evidence custody mismatch')
    retained = state.get('evidence', {})
    for observation in state.get('observations', []):
        request = observation.get('request', {})
        refs = observation.get('evidence_refs', [])
        if (request.get('tool') not in tools or not isinstance(refs, list)
                or not 1 <= len(refs) <= 16 or any(not isinstance(ref, str) for ref in refs)
                or len(refs) != len(set(refs))):
            raise ValueError('Unapproved investigation observation')
        if request.get('tool') == 'read_evidence' and any(ref not in result for ref in refs):
            raise ValueError('Evidence reread cannot promote an author claim')
        for ref in refs:
            document = retained.get(ref)
            if not isinstance(document, dict) or digest(document) != ref:
                raise ValueError('Investigation observation custody mismatch')
            result[ref] = deepcopy(document)
    return result
