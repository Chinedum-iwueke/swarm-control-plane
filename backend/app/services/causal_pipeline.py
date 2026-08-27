from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.causal_pipeline import (
    CausalDatasetMaterialization,
    CausalDatasetPipeline,
)
from app.models.data_contract import ResearchDatasetBuild, ResearchDatasetManifest
from app.models.factor_language import FactorExperimentProgram
from app.schemas.causal_pipeline import (
    CausalMaterializationCreate,
    CausalPipelineCreate,
)
from app.services.research import record_digest


class CausalPipelineConflict(RuntimeError):
    pass


def compile_pipeline(
    payload: CausalPipelineCreate,
    build: ResearchDatasetBuild,
    program: FactorExperimentProgram,
) -> dict:
    specification = payload.specification.model_dump(mode="json")
    if record_digest(specification) != payload.specification_digest:
        raise CausalPipelineConflict(
            "Pipeline specification digest does not match content."
        )
    factor_keys = set(program.compiled.get("factors", {}))
    missing = sorted(
        {item.factor_key for item in payload.specification.features} - factor_keys
    )
    if missing:
        raise CausalPipelineConflict(
            f"Feature bindings reference unknown factors: {', '.join(missing)}."
        )
    label = program.compiled.get("label", {})
    if any(
        item.horizon_bars != label.get("horizon")
        for item in payload.specification.labels
    ):
        raise CausalPipelineConflict(
            "Label horizon differs from the compiled factor program."
        )
    folds = []
    maximum_end = max(
        item.label_end_offset_bars for item in payload.specification.labels
    )
    for fold in payload.specification.split.folds:
        folds.append(
            {
                **fold.model_dump(mode="json"),
                "latest_eligible_train_observation": fold.train_end - maximum_end,
                "purged_interval": [fold.train_end, fold.validation_start],
                "embargo_interval": [
                    fold.validation_end,
                    fold.validation_end + payload.specification.split.embargo_bars,
                ],
            }
        )
    compiled = {
        "schema_version": "causal-feature-label-split-ir-v1.0.0",
        "dataset_build_id": str(build.id),
        "dataset_content_digest": build.content_digest,
        "factor_program_id": str(program.id),
        "factor_program_digest": program.compiled_digest,
        "decision_clock": payload.specification.decision_clock,
        "features": [
            item.model_dump(mode="json") for item in payload.specification.features
        ],
        "labels": [
            item.model_dump(mode="json") for item in payload.specification.labels
        ],
        "fitted_transforms": [
            item.model_dump(mode="json")
            for item in payload.specification.fitted_transforms
        ],
        "sample_weighting": payload.specification.sample_weighting,
        "split": {
            "method": payload.specification.split.method,
            "purge_bars": payload.specification.split.purge_bars,
            "embargo_bars": payload.specification.split.embargo_bars,
            "folds": folds,
        },
        "action_authority": False,
    }
    return compiled


def register_pipeline(
    db: Session, payload: CausalPipelineCreate
) -> CausalDatasetPipeline:
    build = db.get(ResearchDatasetBuild, payload.dataset_build_id)
    program = db.get(FactorExperimentProgram, payload.factor_program_id)
    if build is None or program is None:
        raise CausalPipelineConflict(
            "Registered dataset build and factor program are required."
        )
    manifest = db.get(ResearchDatasetManifest, build.manifest_id)
    if manifest is None or manifest.manifest_digest != program.compiled.get(
        "dataset_manifest_digest"
    ):
        raise CausalPipelineConflict(
            "Dataset build and factor program manifest lineage differ."
        )
    compiled = compile_pipeline(payload, build, program)
    compiled_digest = record_digest(compiled)
    existing = db.scalar(
        select(CausalDatasetPipeline).where(
            or_(
                CausalDatasetPipeline.pipeline_key == payload.pipeline_key,
                CausalDatasetPipeline.specification_digest
                == payload.specification_digest,
                CausalDatasetPipeline.compiled_digest == compiled_digest,
            )
        )
    )
    if existing:
        if existing.compiled_digest == compiled_digest:
            return existing
        raise CausalPipelineConflict("Pipeline key or immutable digest already exists.")
    record = CausalDatasetPipeline(
        pipeline_key=payload.pipeline_key,
        dataset_build_id=payload.dataset_build_id,
        factor_program_id=payload.factor_program_id,
        specification=payload.specification.model_dump(mode="json"),
        specification_digest=payload.specification_digest,
        compiled=compiled,
        compiled_digest=compiled_digest,
        registered_by=payload.registered_by,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        raise CausalPipelineConflict(
            "Pipeline key or immutable digest already exists."
        ) from exc
    return record


def register_materialization(
    db: Session, payload: CausalMaterializationCreate
) -> CausalDatasetMaterialization:
    pipeline = db.get(CausalDatasetPipeline, payload.pipeline_id)
    if pipeline is None:
        raise CausalPipelineConflict("Registered causal pipeline is required.")
    expected_folds = [item["fold"] for item in pipeline.compiled["split"]["folds"]]
    observed_folds = [item.fold for item in payload.fold_results]
    if observed_folds != expected_folds:
        raise CausalPipelineConflict(
            "Materialization fold evidence does not match the pipeline."
        )
    for evidence, contract in zip(
        payload.fold_results, pipeline.compiled["split"]["folds"], strict=True
    ):
        if (
            evidence.maximum_train_label_end
            > contract["latest_eligible_train_observation"]
        ):
            raise CausalPipelineConflict(
                "Materialization leaks a training label across the purge boundary."
            )
        if evidence.minimum_validation_feature_time < contract["validation_start"]:
            raise CausalPipelineConflict(
                "Materialization uses a feature before the validation boundary."
            )
    document = payload.model_dump(mode="json", exclude={"record_digest", "built_by"})
    if record_digest(document) != payload.record_digest:
        raise CausalPipelineConflict(
            "Materialization record digest does not match content."
        )
    existing = db.scalar(
        select(CausalDatasetMaterialization).where(
            or_(
                CausalDatasetMaterialization.materialization_key
                == payload.materialization_key,
                CausalDatasetMaterialization.record_digest == payload.record_digest,
            )
        )
    )
    if existing:
        if existing.record_digest == payload.record_digest:
            return existing
        raise CausalPipelineConflict("Materialization key already exists.")
    record = CausalDatasetMaterialization(**payload.model_dump(mode="python"))
    db.add(record)
    db.flush()
    return record
