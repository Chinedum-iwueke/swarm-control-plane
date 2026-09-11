import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "gov001_bootstrap",
    Path(__file__).parents[1] / "scripts" / "gov001_bootstrap.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_founder_channels_are_bound_to_canonical_operator() -> None:
    manifest = MODULE.build_manifest()

    assert manifest["version"] == "1.0.1"
    assert manifest["identity_aliases"] == {
        "founder-mission-control": "founder-operator",
        "founder-telegram": "founder-operator",
    }
