import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from swarm_worker.models import AgentIdentity, Task
from swarm_worker.strategy_review_contract import AlphaStrategyReviewContract
from swarm_worker.workflows import WorkflowDefinition, WorkflowLoader

_SAFE_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_WORKFLOW = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SAFE_BASE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class WorkerPolicyError(Exception):
    """Base class for task contract and worker policy failures."""


class UnsupportedTaskType(WorkerPolicyError):
    """The worker has no implementation for the task type."""


class RepositoryNotAllowed(WorkerPolicyError):
    """The workflow does not permit the requested repository."""


class MachineNotAllowed(WorkerPolicyError):
    """The task cannot run on this worker's machine."""


class CapabilityMismatch(WorkerPolicyError):
    """The agent does not provide every capability required by the task."""


class RiskCeilingExceeded(WorkerPolicyError):
    """The task risk exceeds the authenticated agent's ceiling."""


class InvalidTaskContract(WorkerPolicyError):
    """The task input contract is malformed or unsafe."""


class CodeValidationContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(
        min_length=1,
        max_length=100,
        pattern=_SAFE_REPOSITORY.pattern,
    )
    workflow: str = Field(
        min_length=1,
        max_length=100,
        pattern=_SAFE_WORKFLOW.pattern,
    )
    base_ref: str = Field(min_length=1, max_length=255)

    @field_validator("base_ref")
    @classmethod
    def validate_base_ref(cls, base_ref: str) -> str:
        return validate_base_ref(base_ref)


class EngineeringMissionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(pattern=_SAFE_REPOSITORY.pattern, max_length=100)
    workflow: Literal["engineering-mission"]
    base_ref: str = Field(min_length=1, max_length=255)
    milestone_id: str = Field(pattern=_SAFE_WORKFLOW.pattern, max_length=100)
    work_item_id: str = Field(pattern=_SAFE_WORKFLOW.pattern, max_length=100)
    objective: str = Field(min_length=10, max_length=4000)
    allowed_paths: list[str] = Field(min_length=1, max_length=50)
    context_paths: list[str] = Field(default_factory=list, max_length=50)
    evidence_context: str = Field(default="{}", max_length=48000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=50)
    stop_conditions: list[str] = Field(min_length=1, max_length=20)
    max_files_changed: int = Field(ge=1, le=100)
    max_diff_lines: int = Field(ge=1, le=10000)
    max_duration_seconds: int = Field(ge=60, le=86400)

    @field_validator("evidence_context")
    @classmethod
    def bounded_evidence(cls, value):
        if len(value.encode()) > 48000:
            raise ValueError("engineering evidence exceeds 48000 bytes")
        try:
            parsed = json.loads(value)
        except RecursionError as error:
            raise ValueError(
                "engineering evidence nesting exceeds safe limits"
            ) from error
        if not isinstance(parsed, dict) or len(parsed) > 20:
            raise ValueError("engineering evidence must be a bounded JSON object")
        pending = [(parsed, 0)]
        while pending:
            node, depth = pending.pop()
            if depth > 32:
                raise ValueError("engineering evidence nesting exceeds safe limits")
            children = (
                node.values()
                if isinstance(node, dict)
                else node
                if isinstance(node, list)
                else ()
            )
            pending.extend((child, depth + 1) for child in children)
        json.dumps(parsed, allow_nan=False)
        return value

    @field_validator("base_ref")
    @classmethod
    def safe_base_ref(cls, value: str) -> str:
        return validate_base_ref(value)

    @field_validator("allowed_paths", "context_paths")
    @classmethod
    def safe_paths(cls, paths: list[str]) -> list[str]:
        for path in paths:
            if (
                path.startswith(("/", ".", "-"))
                or ".." in path.split("/")
                or not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9/_.-]*$", path)
            ):
                raise ValueError("paths must be safe repository-relative paths")
        return paths


class ResearchAcceptanceCriteria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_out_of_sample_sharpe: float = Field(ge=-10, le=10)
    maximum_out_of_sample_drawdown: float = Field(ge=0, le=1)
    minimum_out_of_sample_trades: int = Field(ge=1, le=10000)
    minimum_cost_stress_sharpe: float = Field(ge=-10, le=10)


class ResearchExperimentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Literal["bulletproof_bt"]
    workflow: Literal["research-experiment"]
    base_ref: str = Field(min_length=1, max_length=255)
    program_id: str = Field(pattern=_SAFE_WORKFLOW.pattern, max_length=100)
    hypothesis_id: str = Field(pattern=_SAFE_WORKFLOW.pattern, max_length=100)
    hypothesis: Literal["lagged-return-momentum", "btc-hourly-lagged-return"]
    dataset: Literal["synthetic-regime-v1", "binance-btcusdt-1h-2025"]
    dataset_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    experiment_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    trial_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(ge=0, le=2_147_483_647)
    observations: int = Field(ge=500, le=10000)
    train_fraction: float = Field(ge=0.5, le=0.8)
    transaction_cost_bps: float = Field(ge=0, le=100)
    acceptance: ResearchAcceptanceCriteria

    @model_validator(mode="after")
    def real_data_is_registry_bound(self) -> "ResearchExperimentContract":
        if self.dataset == "binance-btcusdt-1h-2025":
            if self.hypothesis != "btc-hourly-lagged-return":
                raise ValueError(
                    "real-data snapshot requires the approved M13 hypothesis"
                )
            if not all((self.dataset_digest, self.experiment_digest)):
                raise ValueError(
                    "real-data execution requires snapshot and experiment digests"
                )
        return self

    @field_validator("base_ref")
    @classmethod
    def safe_base_ref(cls, value: str) -> str:
        return validate_base_ref(value)


class ResearchMemorySyncContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Literal["bulletproof_bt"]
    workflow: Literal["research-memory-sync"]
    base_ref: str = Field(min_length=1, max_length=255)

    @field_validator("base_ref")
    @classmethod
    def safe_base_ref(cls, value: str) -> str:
        return validate_base_ref(value)


class AlphaResearchDatasetBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_build_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    dataset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_path: str = Field(min_length=1, max_length=1024)
    dataset_key: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150
    )
    instrument: str = Field(pattern=r"^[A-Z0-9_-]+$", max_length=50)
    venue: Literal["bybit", "binance"]

    @field_validator("dataset_path")
    @classmethod
    def admitted_panel_path(cls, value: str) -> str:
        return _admitted_alpha_panel_path(value)


def _admitted_alpha_panel_path(value: str) -> str:
    path = Path(value).resolve(strict=False)
    root = Path("/home/omenka/Projects/bulletproof_bt/research_data").resolve(
        strict=False
    )
    if not path.is_absolute() or path.suffix != ".parquet":
        raise ValueError("dataset_path must identify an absolute Parquet panel")
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("dataset_path is outside the read-only Bulletproof lake") from exc
    return str(path)


class AlphaResearchExecutionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Literal["bulletproof_bt"]
    workflow: Literal["alpha-research-execution"]
    base_ref: str = Field(min_length=40, max_length=64, pattern=r"^[0-9a-f]+$")
    campaign_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    campaign_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_candidate_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    source_candidate_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    question: str = Field(min_length=10, max_length=4000)
    question_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    domain_key: str = Field(pattern=r"^[a-z][a-z0-9-]*$", max_length=100)
    dataset_build_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    dataset_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_path: str = Field(min_length=1, max_length=1024)
    memory_database: Literal[
        "/home/omenka/.local/state/invariance-swarm/alpha002-memory.sqlite"
    ]
    bundle_root: Literal["/home/omenka/.local/share/invariance-swarm/alpha002-bundles"]
    dataset_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", max_length=150)
    dataset_bindings: list[AlphaResearchDatasetBinding] = Field(
        default_factory=list, max_length=20
    )
    instrument: str = Field(pattern=r"^[A-Z0-9_-]+$", max_length=50)
    instruments: list[str] = Field(default_factory=list, max_length=20)
    timeframe: Literal["1m"]
    research_timeframe: str = Field(default="1m", pattern=r"^[1-9][0-9]*[mhd]$")
    resampling_policy: Literal["right_closed_left_labeled_complete_bars"] = (
        "right_closed_left_labeled_complete_bars"
    )
    reusable_strategy: dict[str, Any] | None = None
    tier: Literal["Tier2A", "Tier2B", "Tier3"]
    max_variants: int = Field(ge=1, le=256)
    research_context: dict[str, Any]
    authority: Literal["no_capital"]
    stage: Literal["draft", "qualify", "execute"] = "execute"
    venue: Literal["bybit", "binance"] | None = None
    window_start: str | None = None
    window_end: str | None = None
    hypothesis_card: dict[str, Any] | None = None
    card_approval: dict[str, Any] | None = None
    qualification: dict[str, Any] | None = None
    execution_class: Literal["qualification", "commissioning"] = "qualification"

    @model_validator(mode="after")
    def stage_contract(self):
        if self.reusable_strategy is not None:
            reusable = self.reusable_strategy
            required = {
                "hypothesis_id",
                "strategy",
                "input_mode",
                "maximum_instruments",
                "contract_path",
                "contract_digest",
                "variant_count",
                "bounded_weekly_reuse_eligible",
            }
            if not required.issubset(reusable):
                raise ValueError("reusable strategy binding is incomplete")
            if reusable["bounded_weekly_reuse_eligible"] is not True:
                raise ValueError("reusable strategy is not weekly eligible")
            if int(reusable["variant_count"]) > self.max_variants:
                raise ValueError("reusable strategy exceeds assignment variant budget")
            if len(self.instruments or [self.instrument]) > int(
                reusable["maximum_instruments"]
            ):
                raise ValueError("reusable strategy input cardinality mismatch")
            if reusable["input_mode"] == "single_instrument" and len(
                self.instruments or [self.instrument]
            ) != 1:
                raise ValueError("single-instrument strategy cannot consume a basket")
        if (self.stage in {"draft", "qualify"} or self.qualification is not None) and (
            self.window_start is None or self.window_end is None or self.venue is None
        ):
            raise ValueError(
                "governed stages require venue and an immutable execution window"
            )
        if self.stage == "qualify" and (
            self.hypothesis_card is None or self.card_approval is None
        ):
            raise ValueError("qualification requires a draft card and founder approval")
        if (
            self.stage == "execute"
            and self.qualification is not None
            and self.qualification.get("qualified") is not True
        ):
            raise ValueError("execution requires a qualified strategy contract")
        if self.execution_class == "commissioning":
            if self.stage != "execute" or self.qualification is None:
                raise ValueError(
                    "commissioning requires a qualified execute-stage strategy"
                )
            if self.window_start is None or self.window_end is None:
                raise ValueError("commissioning requires an immutable bounded window")
            start = datetime.fromisoformat(self.window_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.window_end.replace("Z", "+00:00"))
            if start.tzinfo is None or end.tzinfo is None:
                raise ValueError("commissioning window timestamps must include a timezone")
            if end <= start or end - start > timedelta(days=31):
                raise ValueError("commissioning window must be positive and at most 31 days")
            reviewed_window = self.qualification.get("window")
            if not isinstance(reviewed_window, dict):
                raise ValueError("commissioning requires the reviewed execution window")
            reviewed_start = datetime.fromisoformat(
                str(reviewed_window.get("start", "")).replace("Z", "+00:00")
            )
            reviewed_end = datetime.fromisoformat(
                str(reviewed_window.get("end", "")).replace("Z", "+00:00")
            )
            if reviewed_start.tzinfo is None or reviewed_end.tzinfo is None:
                raise ValueError("reviewed window timestamps must include a timezone")
            if start < reviewed_start or end > reviewed_end:
                raise ValueError(
                    "commissioning window must be contained by the reviewed window"
                )
            if self.max_variants > 8:
                raise ValueError("commissioning permits at most eight variants")
        if self.dataset_bindings:
            primary = self.dataset_bindings[0]
            if any(
                (
                    self.dataset_build_id != primary.dataset_build_id,
                    self.dataset_digest != primary.dataset_digest,
                    self.dataset_path != primary.dataset_path,
                    self.dataset_key != primary.dataset_key,
                    self.instrument != primary.instrument,
                )
            ):
                raise ValueError("primary dataset fields must match the first binding")
            binding_instruments = [item.instrument for item in self.dataset_bindings]
            if self.instruments != binding_instruments:
                raise ValueError("instrument basket must match dataset binding order")
            if len(binding_instruments) != len(set(binding_instruments)):
                raise ValueError("instrument basket must be unique")
        elif self.instruments and self.instruments != [self.instrument]:
            raise ValueError("legacy single-panel assignment cannot declare a basket")
        return self

    @field_validator("dataset_path")
    @classmethod
    def admitted_panel_path(cls, value: str) -> str:
        return _admitted_alpha_panel_path(value)


class AlphaDiscoveryContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Literal["swarm-control-plane"]
    workflow: Literal["alpha-discovery"]
    base_ref: str = Field(min_length=1, max_length=255)
    stage: Literal["intelligence", "hypothesis", "representation"]
    mandate_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    mandate_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    cycle_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    maximum_candidates: int = Field(ge=2, le=20)
    context: dict[str, Any]
    authority: Literal["no_capital_research"]

    @field_validator("base_ref")
    @classmethod
    def safe_base_ref(cls, value: str) -> str:
        return validate_base_ref(value)


class AlphaDataAdmissionAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    venue: Literal["bybit", "binance"]
    instrument: str = Field(pattern=r"^[A-Z0-9_-]+$", max_length=50)
    timeframe: Literal["1m"] = "1m"


class AlphaDataAdmissionContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Literal["bulletproof_bt"]
    workflow: Literal["alpha-data-admission"]
    base_ref: str = Field(min_length=40, max_length=40, pattern=r"^[0-9a-f]{40}$")
    candidate_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    candidate_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    catalog_receipt_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    catalog_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_commit: str = Field(min_length=40, max_length=40, pattern=r"^[0-9a-f]{40}$")
    data_root: Literal["/home/omenka/Projects/bulletproof_bt/research_data"]
    backup_root: Literal[
        "/home/omenka/.local/share/invariance-swarm/alpha-data-backups"
    ]
    assets: list[AlphaDataAdmissionAsset] = Field(min_length=1, max_length=20)
    authority: Literal["no_capital_data_admission"]

    @model_validator(mode="after")
    def exact_source_and_unique_assets(self):
        if self.base_ref != self.source_commit:
            raise ValueError(
                "data admission source commit must equal the exact base ref"
            )
        identities = [
            (item.venue, item.instrument, item.timeframe) for item in self.assets
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("data admission assets must be unique")
        return self


class ValidatedTaskPolicy(BaseModel):
    contract: (
        CodeValidationContract
        | EngineeringMissionContract
        | ResearchExperimentContract
        | ResearchMemorySyncContract
        | AlphaResearchExecutionContract
        | AlphaDiscoveryContract
        | AlphaDataAdmissionContract
        | AlphaStrategyReviewContract
    )
    workflow: WorkflowDefinition


def validate_base_ref(base_ref: str) -> str:
    if base_ref.startswith("-"):
        raise ValueError("base_ref must not begin with '-'")
    if not _SAFE_BASE_REF.fullmatch(base_ref):
        raise ValueError("base_ref contains unsafe characters")
    if (
        ".." in base_ref
        or "//" in base_ref
        or "@{" in base_ref
        or base_ref.endswith(("/", ".", ".lock"))
    ):
        raise ValueError("base_ref is not a safe Git reference")
    return base_ref


def validate_task_policy(
    task: Task,
    identity: AgentIdentity,
    workflow_loader: WorkflowLoader,
    *,
    worker_machine: str,
) -> ValidatedTaskPolicy:
    if task.task_type not in {
        "code_validation",
        "engineering_mission",
        "research_experiment",
        "research_memory_sync",
        "alpha_research_execution",
        "alpha_discovery",
        "alpha_data_admission",
        "alpha_strategy_review",
    }:
        raise UnsupportedTaskType(f"Task type {task.task_type!r} is not supported.")

    contract = _parse_contract(task.task_type, task.input_contract)
    workflow = workflow_loader.load(contract.workflow)

    if workflow.task_type != task.task_type:
        raise UnsupportedTaskType("Workflow task type does not match the leased task.")
    if contract.repository not in workflow.allowed_repositories:
        raise RepositoryNotAllowed(
            f"Repository {contract.repository!r} is not allowed by the workflow."
        )
    if task.allowed_machines and worker_machine not in task.allowed_machines:
        raise MachineNotAllowed(f"Task is not allowed on machine {worker_machine!r}.")

    missing_capabilities = sorted(
        set(task.required_capabilities) - set(identity.capabilities)
    )
    if missing_capabilities:
        raise CapabilityMismatch(
            "Agent is missing required capabilities: " + ", ".join(missing_capabilities)
        )
    if task.risk_level > identity.risk_ceiling:
        raise RiskCeilingExceeded(
            f"Task risk {task.risk_level} exceeds agent ceiling "
            f"{identity.risk_ceiling}."
        )

    return ValidatedTaskPolicy(contract=contract, workflow=workflow)


def _parse_contract(
    task_type: str, input_contract: dict[str, Any]
) -> (
    CodeValidationContract
    | EngineeringMissionContract
    | ResearchExperimentContract
    | ResearchMemorySyncContract
    | AlphaResearchExecutionContract
    | AlphaDiscoveryContract
    | AlphaDataAdmissionContract
    | AlphaStrategyReviewContract
):
    try:
        models = {
            "code_validation": CodeValidationContract,
            "engineering_mission": EngineeringMissionContract,
            "research_experiment": ResearchExperimentContract,
            "research_memory_sync": ResearchMemorySyncContract,
            "alpha_research_execution": AlphaResearchExecutionContract,
            "alpha_discovery": AlphaDiscoveryContract,
            "alpha_data_admission": AlphaDataAdmissionContract,
            "alpha_strategy_review": AlphaStrategyReviewContract,
        }
        model = models[task_type]
        return model.model_validate(input_contract)
    except ValidationError as exc:
        summary = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise InvalidTaskContract(
            f"Task input contract failed validation: {summary}"
        ) from exc
