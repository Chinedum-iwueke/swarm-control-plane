"""Reconstruct the exact design-diagnostic evidence projection for custody checks."""
import re


def referenced_catalog(payload, catalog, digest):
    if any(digest(value) != key for key, value in catalog.items()):
        raise ValueError('diagnostic catalog custody mismatch')
    selected = {}
    pending = [payload]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.values())
            pending.extend(value.keys())
        elif isinstance(value, list):
            pending.extend(value)
        elif isinstance(value, str):
            for key in re.findall(r'(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])', value):
                if key in catalog and key not in selected:
                    selected[key] = catalog[key]
                    pending.append(catalog[key])
    return selected
