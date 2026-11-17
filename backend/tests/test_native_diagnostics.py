from copy import deepcopy

import pytest

from app.services.graph import digest_document as digest
from app.services.native_diagnostics import verify_diagnostic


def fixture():
    request = {'source_commit': 'a'*40, 'subject_digest': 'b'*64, 'tool': 'design_adequacy_v1'}
    receipt = dict(schema_version='native-diagnostic-receipt-v1', tool=request['tool'],
        source_commit=request['source_commit'], subject_digest=request['subject_digest'],
        request_digest=digest(request), evidence_catalog_digest=digest({}),
        implementation_digests={'diagnostic_tools.py': 'c'*64}, result={'status': 'requires_review'},
        evidence_kind='design_diagnostic', execution_authority=False, scientific_certification=False,
        market_data_used=False)
    return request, receipt | {'receipt_digest': digest(receipt)}


def test_valid_receipt_is_custody_not_approval():
    request, receipt = fixture()
    assert verify_diagnostic(receipt, request, {}, 'a'*40, 'b'*64) == receipt


@pytest.mark.parametrize('field,value', [('source_commit', 'd'*40), ('subject_digest','d'*64),
    ('request_digest','d'*64), ('evidence_catalog_digest','d'*64), ('execution_authority', True),
    ('scientific_certification',True), ('market_data_used',True), ('evidence_kind','observed_market'),
    ('implementation_digests',{}), ('tool','other')])
def test_rehashed_substitution_or_authority_escalation_rejected(field, value):
    request, receipt = fixture()
    receipt[field] = value
    receipt['receipt_digest'] = digest({k:v for k,v in receipt.items() if k!='receipt_digest'})
    with pytest.raises(ValueError): verify_diagnostic(receipt, request, {}, 'a'*40, 'b'*64)


def test_result_tampering_rejected():
    request, receipt = fixture()
    receipt['result']['status'] = 'approved'
    with pytest.raises(ValueError): verify_diagnostic(receipt, request, {}, 'a'*40, 'b'*64)


def test_nested_approval_cannot_be_laundered_by_rehashing():
    request, receipt = fixture()
    receipt['result']['assessment'] = {'scientific_certification': True}
    receipt['receipt_digest'] = digest({k:v for k,v in receipt.items() if k!='receipt_digest'})
    with pytest.raises(ValueError): verify_diagnostic(receipt, request, {}, 'a'*40, 'b'*64)
