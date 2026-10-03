import pytest
from worker.scripts.alpha001_bootstrap import (
    catalog_instrument_matches,
    historical_binding,
)


class Client:
    def __init__(self, campaigns, mandates=None):
        self.campaigns = campaigns
        self.mandates = mandates or []

    def request(self, method, path, json=None):
        assert method == "GET"
        assert path in {
            "/v1/research/alpha-campaigns?limit=200",
            "/v1/research/alpha-discovery/mandates",
        }

        class Response:
            is_error = False

            def __init__(self, document):
                self.document = document

            def json(self):
                return self.document

        return Response(
            self.campaigns
            if path == "/v1/research/alpha-campaigns?limit=200"
            else self.mandates
        )


def test_historical_binding_recovers_exact_prior_custody() -> None:
    binding = {
        "catalog_id": "catalog",
        "lake_governance_snapshot_id": "lake",
        "dataset_key": "panel",
        "partition_digests": ["a" * 64],
    }
    client = Client([{"specification": {"dataset_bindings": [binding]}}])

    assert historical_binding(client, "a" * 64) == binding


def test_historical_binding_rejects_ambiguous_custody() -> None:
    campaigns = [
        {
            "specification": {
                "dataset_bindings": [
                    {
                        "catalog_id": catalog,
                        "lake_governance_snapshot_id": "lake",
                        "dataset_key": "panel",
                        "partition_digests": ["a" * 64],
                    }
                ]
            }
        }
        for catalog in ("one", "two")
    ]

    with pytest.raises(RuntimeError, match="ambiguous recovery"):
        historical_binding(Client(campaigns), "a" * 64)


def test_catalog_instrument_identity_accepts_typed_canonical_id_only() -> None:
    assert catalog_instrument_matches("crypto:tiausdt-perpetual", "TIAUSDT")
    assert not catalog_instrument_matches("crypto:nottiausdt-perpetual", "TIAUSDT")
