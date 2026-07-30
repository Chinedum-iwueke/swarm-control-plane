from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import signal
import stat
import sys
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any, TextIO

from pydantic import ValidationError as PydanticValidationError

from swarm_worker.api_client import AuthenticationError, SwarmAPIClient
from swarm_worker.config import WorkerSettings
from swarm_worker.daemon import (
    EXIT_AUTHENTICATION_ERROR,
    EXIT_CONFIGURATION_ERROR,
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    WorkerDaemon,
)
from swarm_worker.role_package import load_role_package
from swarm_worker.service import (
    AgentDisabled,
    IdentityMismatch,
    WorkerConfigurationError,
    WorkerService,
)
from swarm_worker.workflows import WORKFLOW_FILES, WorkflowLoader

_TOKEN_PATTERN = re.compile(r"\bswarm_(?:ag|lt)_[A-Za-z0-9_-]+\b")
_BEARER_PATTERN = re.compile(r"\bBearer\s+\S+", re.IGNORECASE)
_AUTHORIZATION_PATTERN = re.compile(
    r"Authorization\s*:\s*\S+(?:\s+\S+)?",
    re.IGNORECASE,
)


class RedactingJSONFormatter(logging.Formatter):
    def __init__(self, *, secrets: Sequence[str] = ()) -> None:
        super().__init__()
        self._secrets = tuple(secret for secret in secrets if secret)

    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": self._redact(record.getMessage()),
        }
        for key in (
            "error_category",
            "exit_code",
            "outcome",
            "retry_delay_seconds",
        ):
            value = getattr(record, key, None)
            if value is not None:
                document[key] = self._redact(value) if isinstance(value, str) else value
        return json.dumps(document, ensure_ascii=True, sort_keys=True)

    def _redact(self, value: str) -> str:
        for secret in self._secrets:
            value = value.replace(secret, "[REDACTED]")
        value = _TOKEN_PATTERN.sub("[REDACTED]", value)
        value = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
        return _AUTHORIZATION_PATTERN.sub(
            "Authorization: [REDACTED]",
            value,
        )


def configure_logging(
    level: str,
    *,
    secrets: Sequence[str] = (),
    stream: TextIO = sys.stderr,
) -> logging.Logger:
    logger = logging.getLogger("swarm_worker")
    logger.handlers.clear()
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingJSONFormatter(secrets=secrets))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper()))
    return logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invariance-swarm-worker")
    parser.add_argument("--log-level", choices=_log_levels(), default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "once", "check"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--log-level",
            dest="command_log_level",
            choices=_log_levels(),
            default=None,
        )
    return parser


async def run_cli(
    args: argparse.Namespace,
    *,
    settings_loader: Callable[[], WorkerSettings] = WorkerSettings,
    api_client_factory: Callable[[WorkerSettings], Any] = SwarmAPIClient,
    service_factory: Callable[[WorkerSettings], WorkerService] | None = None,
    daemon_factory: Callable[
        [WorkerService, WorkerSettings, logging.Logger],
        WorkerDaemon,
    ]
    | None = None,
    stream: TextIO = sys.stderr,
) -> int:
    level = args.command_log_level or args.log_level or "INFO"
    try:
        settings = settings_loader()
    except PydanticValidationError:
        logger = configure_logging(level, stream=stream)
        logger.critical(
            "configuration_failed",
            extra={"exit_code": EXIT_CONFIGURATION_ERROR},
        )
        return EXIT_CONFIGURATION_ERROR

    logger = configure_logging(
        level,
        secrets=(settings.swarm_agent_token,),
        stream=stream,
    )
    service_builder = service_factory or (
        lambda configured: WorkerService(
            settings_loader=lambda: configured,
            api_client_factory=api_client_factory,
        )
    )

    if args.command == "check":
        return await check_worker(
            settings,
            api_client_factory=api_client_factory,
            logger=logger,
        )

    service = service_builder(settings)
    if args.command == "once":
        try:
            outcome = await service.run_once()
        except AuthenticationError:
            logger.critical(
                "authentication_failed",
                extra={"exit_code": EXIT_AUTHENTICATION_ERROR},
            )
            return EXIT_AUTHENTICATION_ERROR
        except WorkerConfigurationError:
            logger.critical(
                "configuration_failed",
                extra={"exit_code": EXIT_CONFIGURATION_ERROR},
            )
            return EXIT_CONFIGURATION_ERROR
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            logger.error(
                "worker_once_failed",
                extra={
                    "error_category": type(exc).__name__,
                    "exit_code": EXIT_RUNTIME_ERROR,
                },
            )
            return EXIT_RUNTIME_ERROR
        logger.info("worker_once_complete", extra={"outcome": outcome.status})
        return EXIT_OK

    daemon_builder = daemon_factory or _default_daemon
    daemon = daemon_builder(service, settings, logger)
    _install_signal_handlers(daemon)
    return await daemon.run()


async def check_worker(
    settings: WorkerSettings,
    *,
    api_client_factory: Callable[[WorkerSettings], Any] = SwarmAPIClient,
    logger: logging.Logger | None = None,
) -> int:
    active_logger = logger or logging.getLogger("swarm_worker")
    try:
        settings.prepare_directories()
        _verify_roots(settings)
        workflow_loader = WorkflowLoader(settings.swarm_workflow_directory)
        for workflow_name in WORKFLOW_FILES:
            workflow_loader.load(workflow_name)
        role_package = load_role_package(
            settings.swarm_role_package_manifest,
            settings.swarm_workflow_directory,
        )
        if "engineering_mission" in role_package.manifest.task_types:
            _verify_engineering_runtime(settings)

        api = api_client_factory(settings)
        try:
            identity = await api.get_identity()
        finally:
            await api.aclose()
        _verify_identity(identity, settings)
        manifest = role_package.manifest
        if settings.swarm_machine not in manifest.allowed_machines:
            raise WorkerConfigurationError(
                "Role package does not allow the configured machine."
            )
        if not set(manifest.required_capabilities).issubset(identity.capabilities):
            raise WorkerConfigurationError(
                "Agent identity lacks role-package capabilities."
            )
        if identity.risk_ceiling > manifest.risk_ceiling:
            raise WorkerConfigurationError(
                "Agent risk ceiling exceeds role-package ceiling."
            )
    except AuthenticationError:
        active_logger.critical(
            "authentication_failed",
            extra={"exit_code": EXIT_AUTHENTICATION_ERROR},
        )
        return EXIT_AUTHENTICATION_ERROR
    except (WorkerConfigurationError, IdentityMismatch, AgentDisabled):
        active_logger.error(
            "worker_check_configuration_failed",
            extra={"exit_code": EXIT_CONFIGURATION_ERROR},
        )
        return EXIT_CONFIGURATION_ERROR
    except Exception as exc:  # noqa: BLE001 - diagnostic command boundary
        active_logger.error(
            "worker_check_failed",
            extra={
                "error_category": type(exc).__name__,
                "exit_code": EXIT_RUNTIME_ERROR,
            },
        )
        return EXIT_RUNTIME_ERROR

    active_logger.info("worker_check_succeeded")
    return EXIT_OK


def _verify_roots(settings: WorkerSettings) -> None:
    repository_root = settings.swarm_repository_root.resolve(strict=True)
    if not repository_root.is_dir():
        raise WorkerConfigurationError("Repository root is not a directory.")

    workspace_root = settings.swarm_workspace_root.resolve(strict=True)
    if not workspace_root.is_dir():
        raise WorkerConfigurationError("Workspace root is not a directory.")
    mode = stat.S_IMODE(workspace_root.stat().st_mode)
    if mode & 0o077:
        raise WorkerConfigurationError(
            "Workspace root permissions must not allow group or other access."
        )
    if not os.access(workspace_root, os.R_OK | os.W_OK | os.X_OK):
        raise WorkerConfigurationError("Workspace root is not accessible.")


def _verify_engineering_runtime(settings: WorkerSettings) -> None:
    if shutil.which("codex") is None:
        raise WorkerConfigurationError("Codex executable is unavailable.")
    try:
        codex_home = settings.swarm_codex_home.resolve(strict=True)
    except OSError as exc:
        raise WorkerConfigurationError("Codex worker home is unavailable.") from exc
    if not codex_home.is_dir():
        raise WorkerConfigurationError("Codex worker home is not a directory.")
    mode = stat.S_IMODE(codex_home.stat().st_mode)
    if mode & 0o077:
        raise WorkerConfigurationError(
            "Codex worker home must not be accessible by group or others."
        )


def _verify_identity(identity: Any, settings: WorkerSettings) -> None:
    if not identity.is_enabled:
        raise AgentDisabled("Authenticated agent is disabled.")
    if (
        identity.slug != settings.swarm_agent_slug
        or identity.machine != settings.swarm_machine
    ):
        raise IdentityMismatch(
            "Authenticated identity does not match worker configuration."
        )


def _default_daemon(
    service: WorkerService,
    settings: WorkerSettings,
    logger: logging.Logger,
) -> WorkerDaemon:
    return WorkerDaemon(
        service,
        poll_interval_seconds=settings.swarm_poll_interval_seconds,
        logger=logger.getChild("daemon"),
    )


def _install_signal_handlers(daemon: WorkerDaemon) -> None:
    loop = asyncio.get_running_loop()
    for requested_signal in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(
                requested_signal,
                daemon.request_shutdown,
            )
        except NotImplementedError:
            pass


def _log_levels() -> tuple[str, ...]:
    return ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(run_cli(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
