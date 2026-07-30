import asyncio
import json
from pathlib import Path

from pydantic import ValidationError

from swarm_worker.models import BrokerExecutionResult, BrokerTicketResponse


class BrokerClientError(Exception):
    """The local privileged broker rejected or failed an operation."""


class BrokerClient:
    def __init__(self, socket_path: Path, *, timeout_seconds: float = 180) -> None:
        self._socket_path = socket_path
        self._timeout = timeout_seconds

    async def execute(self, ticket: BrokerTicketResponse) -> BrokerExecutionResult:
        writer: asyncio.StreamWriter | None = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self._socket_path),
                timeout=5,
            )
            writer.write(
                (
                    json.dumps(ticket.model_dump(mode="json"), sort_keys=True) + "\n"
                ).encode()
            )
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=self._timeout)
        except (OSError, TimeoutError) as exc:
            raise BrokerClientError(
                f"Broker connection failed: {type(exc).__name__}"
            ) from exc
        finally:
            if writer is not None:
                writer.close()
                await writer.wait_closed()
        try:
            document = json.loads(line)
            if document.get("ok") is not True:
                raise BrokerClientError(
                    f"Broker rejected operation: {document.get('error', 'unknown')}"
                )
            return BrokerExecutionResult.model_validate(document["result"])
        except (json.JSONDecodeError, KeyError, AttributeError, ValidationError) as exc:
            raise BrokerClientError("Broker response is invalid.") from exc
