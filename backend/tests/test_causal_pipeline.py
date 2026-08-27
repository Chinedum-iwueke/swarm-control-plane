from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.api.routes.causal_pipelines import router
from app.schemas.causal_pipeline import (
    CausalMaterializationCreate,
    CausalPipelineCreate,
)
from app.services.causal_pipeline import (
    CausalPipelineConflict,
    compile_pipeline,
    register_materialization,
    register_pipeline,
)
from app.services.research import record_digest
from pydantic import ValidationError

BUILD_ID = uuid4()
PROGRAM_ID = uuid4()
PIPELINE_ID = uuid4()


def specification(**updates):
    value = {
        "schema_version": "causal-feature-label-split-v1.0.0",
        "decision_clock": "decision_close",
        "features": [
            {
                "feature_key": "momentum",
                "factor_key": "lagged_return",
                "availability_lag_bars": 1,
                "missing_policy": "drop",
            }
        ],
        "labels": [
            {
                "label_key": "next_return",
                "kind": "forward_return",
                "horizon_bars": 2,
                "label_end_offset_bars": 2,
            }
        ],
        "fitted_transforms": [
            {"transform_key": "scale", "kind": "standardize", "fit_scope": "train_only"}
        ],
        "split": {
            "method": "expanding_walk_forward",
            "purge_bars": 2,
            "embargo_bars": 2,
            "folds": [
                {
                    "fold": 1,
                    "train_start": 0,
                    "train_end": 100,
                    "validation_start": 102,
                    "validation_end": 120,
                },
                {
                    "fold": 2,
                    "train_start": 0,
                    "train_end": 120,
                    "validation_start": 122,
                    "validation_end": 140,
                },
            ],
        },
        "sample_weighting": "inverse_label_overlap",
        "action_authority": False,
    }
    value.update(updates)
    return value


def pipeline_payload(**updates):
    spec = specification(**updates)
    return CausalPipelineCreate.model_validate(
        {
            "pipeline_key": "ML002-PILOT",
            "dataset_build_id": BUILD_ID,
            "factor_program_id": PROGRAM_ID,
            "specification": spec,
            "specification_digest": record_digest(spec),
            "registered_by": "ml002-pilot",
        }
    )


def build_and_program():
    build = SimpleNamespace(id=BUILD_ID, manifest_id=uuid4(), content_digest="a" * 64)
    program = SimpleNamespace(
        id=PROGRAM_ID,
        compiled={
            "factors": {"lagged_return": {}},
            "label": {"horizon": 2},
            "dataset_manifest_digest": "b" * 64,
        },
        compiled_digest="c" * 64,
    )
    return build, program


def materialization(**updates):
    value = {
        "materialization_key": "ML002-PILOT-MATERIALIZATION",
        "pipeline_id": PIPELINE_ID,
        "output_uri": "file:///evidence/ml002.parquet",
        "row_count": 100,
        "fold_results": [
            {
                "fold": 1,
                "train_rows": 98,
                "validation_rows": 18,
                "maximum_train_label_end": 98,
                "minimum_validation_feature_time": 102,
                "purge_passed": True,
                "embargo_passed": True,
                "train_only_fit_passed": True,
                "point_in_time_join_passed": True,
            },
            {
                "fold": 2,
                "train_rows": 118,
                "validation_rows": 18,
                "maximum_train_label_end": 118,
                "minimum_validation_feature_time": 122,
                "purge_passed": True,
                "embargo_passed": True,
                "train_only_fit_passed": True,
                "point_in_time_join_passed": True,
            },
        ],
        "content_digest": "d" * 64,
        "rebuild_content_digest": "d" * 64,
        "built_by": "ml002-pilot",
    }
    value.update(updates)
    digest_document = {
        key: (str(item) if key == "pipeline_id" else item)
        for key, item in value.items()
        if key not in {"record_digest", "built_by"}
    }
    value["record_digest"] = record_digest(digest_document)
    return CausalMaterializationCreate.model_validate(value)


def test_compile_is_deterministic_and_binds_lineage():
    payload = pipeline_payload()
    build, program = build_and_program()
    first = compile_pipeline(payload, build, program)
    assert first == compile_pipeline(payload, build, program)
    assert first["dataset_content_digest"] == "a" * 64
    assert first["factor_program_digest"] == "c" * 64
    assert first["split"]["folds"][0]["latest_eligible_train_observation"] == 98
    assert first["action_authority"] is False


def test_purge_must_cover_label_end():
    request = specification()
    request["split"]["purge_bars"] = 1
    with pytest.raises(ValidationError, match="purge_bars"):
        pipeline_payload(**request)


def test_embargo_must_separate_validation_folds():
    request = specification()
    request["split"]["folds"][1]["validation_start"] = 121
    request["split"]["folds"][1]["train_end"] = 119
    with pytest.raises(ValidationError, match="embargo"):
        pipeline_payload(**request)


def test_fit_scope_cannot_use_validation_rows():
    request = specification()
    request["fitted_transforms"][0]["fit_scope"] = "all_rows"
    with pytest.raises(ValidationError):
        pipeline_payload(**request)


def test_program_factor_and_label_must_match():
    build, program = build_and_program()
    program.compiled["factors"] = {"other": {}}
    with pytest.raises(CausalPipelineConflict, match="unknown factors"):
        compile_pipeline(pipeline_payload(), build, program)


def test_registration_rejects_dataset_lineage_drift():
    db = MagicMock()
    build, program = build_and_program()
    db.get.side_effect = [build, program, SimpleNamespace(manifest_digest="e" * 64)]
    with pytest.raises(CausalPipelineConflict, match="lineage differ"):
        register_pipeline(db, pipeline_payload())


def test_materialization_rejects_rebuild_drift():
    with pytest.raises(ValidationError, match="rebuild digest"):
        materialization(rebuild_content_digest="e" * 64)


def test_materialization_rejects_leaking_observation():
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        compiled={
            "split": {
                "folds": [
                    {
                        "fold": 1,
                        "latest_eligible_train_observation": 98,
                        "validation_start": 102,
                    },
                    {
                        "fold": 2,
                        "latest_eligible_train_observation": 118,
                        "validation_start": 122,
                    },
                ]
            }
        }
    )
    leaking = materialization()
    leaking.fold_results[0].maximum_train_label_end = 99
    with pytest.raises(CausalPipelineConflict, match="leaks"):
        register_materialization(db, leaking)


def test_routes_are_registered():
    assert {route.path for route in router.routes} == {
        "/v1/research/causal-pipelines",
        "/v1/research/causal-pipelines/{pipeline_id}",
        "/v1/research/causal-pipelines/materializations",
        "/v1/research/causal-pipelines/materializations/{materialization_id}",
    }
