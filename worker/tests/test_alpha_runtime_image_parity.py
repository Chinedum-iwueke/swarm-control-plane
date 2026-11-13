import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "runtime_parity", Path(__file__).parents[1] / "scripts/verify_alpha_runtime_images.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def records():
    return [{"Name": "/" + name, "Image": "sha256:" + "a" * 64,
             "State": {"Running": True, "Restarting": False}}
            for name in module.RUNTIMES]


def test_all_decision_producers_must_match_built_image():
    values = records()
    assert module.verify(values, "sha256:" + "a" * 64)["success"]
    values[1]["Image"] = "sha256:" + "b" * 64
    report = module.verify(values, "sha256:" + "a" * 64)
    assert not report["success"]
    assert report["failures"] == [module.RUNTIMES[1] + ":stale_image"]


@pytest.mark.parametrize("state", [
    {"Running": False}, {"Running": True, "Restarting": True},
    {"Running": True, "Health": {"Status": "unhealthy"}},
    {"Running": True, "Health": {"Status": "starting"}},
])
def test_inactive_or_unhealthy_runtime_fails(state):
    values = records()
    values[0]["State"] = state
    assert not module.verify(values, "sha256:" + "a" * 64)["success"]


def test_missing_runtime_and_unbound_image_fail():
    assert not module.verify(records()[:2], "sha256:" + "a" * 64)["success"]
    assert not module.verify(records(), "latest")["success"]


def test_director_inherited_http_probe_is_not_misreported_as_readiness():
    values = records()
    values[1]["State"]["Health"] = {"Status": "unhealthy"}
    report = module.verify(values, "sha256:" + "a" * 64)
    assert report["success"]
    assert report["warnings"] == [module.RUNTIMES[1] + ":inherited_api_healthcheck_not_director_readiness"]
