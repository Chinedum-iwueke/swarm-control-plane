"""Lossless bounded method-result transport; mirror in backend contracts."""
import base64
import hashlib
import json
import zlib

WIRE_LIMIT = 262144
EXPANDED_LIMIT = 524288
FORMAT = 'method-task-result-v3'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def encode(value):
    raw = canonical(value)
    if len(json.dumps(value, sort_keys=True).encode()) < WIRE_LIMIT - 1024:
        return value
    if len(raw) > EXPANDED_LIMIT or value.get('schema_version') != 'method-task-result-v2':
        raise ValueError('Method result exceeds bounded expanded transport')
    result = dict(schema_version=FORMAT, contract_digest=value['contract_digest'],
        scientific_approval=False, execution_authority=False, expanded_bytes=len(raw),
        expanded_digest=hashlib.sha256(raw).hexdigest(),
        payload=base64.b64encode(zlib.compress(raw)).decode('ascii'))
    result['result_digest'] = digest(result)
    if len(canonical(result)) > WIRE_LIMIT - 1024:
        raise ValueError('Method result exceeds wire transport')
    return result


def decode(value):
    if value.get('schema_version') != FORMAT:
        return value
    if (set(value) != {'schema_version','contract_digest','scientific_approval',
            'execution_authority','expanded_bytes','expanded_digest','payload','result_digest'}
            or len(canonical(value)) > WIRE_LIMIT
            or type(value['expanded_bytes']) is not int
            or not 0 < value['expanded_bytes'] <= EXPANDED_LIMIT
            or value['scientific_approval'] is not False or value['execution_authority'] is not False
            or digest({k:v for k,v in value.items() if k != 'result_digest'}) != value['result_digest']):
        raise ValueError('Invalid method result transport')
    try:
        compressed = base64.b64decode(value['payload'], validate=True)
        inflater = zlib.decompressobj()
        raw = inflater.decompress(compressed, EXPANDED_LIMIT + 1)
    except (ValueError, TypeError, zlib.error) as exc:
        raise ValueError('Invalid method result compression') from exc
    if (len(raw) != value['expanded_bytes'] or not inflater.eof or inflater.unused_data
            or inflater.unconsumed_tail or len(raw) > EXPANDED_LIMIT
            or hashlib.sha256(raw).hexdigest() != value['expanded_digest']):
        raise ValueError('Method result expansion or integrity failure')
    def pairs(items):
        result = {}
        for key, child in items:
            if key in result:
                raise ValueError('Duplicate method transport key')
            result[key] = child
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError('Invalid method result JSON') from exc
    if (not isinstance(result, dict) or result.get('schema_version') != 'method-task-result-v2'
            or result.get('contract_digest') != value['contract_digest']
            or canonical(result) != raw):
        raise ValueError('Method result transport binding mismatch')
    return result
