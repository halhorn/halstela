"""Command Worker Lambda ハンドラー

Skill Lambda から非同期に起動され、Tesla へのコマンド実行を担う。
"""

from __future__ import annotations

import logging
from typing import Any

from halstela.clients.tesla_fleet_client import create_fleet_client
from halstela.config import TeslaConfig
from halstela.models.worker_command import WorkerCommand
from halstela.services.vehicle_service import VehicleService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# コマンド名 → VehicleService のメソッド名
_COMMAND_HANDLERS: dict[str, str] = {
    "auto_conditioning_start": "start_air_conditioning",
}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    command = WorkerCommand.from_payload(event)
    # access_token を含むためペイロード全体はログしない
    logger.info(
        "Worker command received: command=%s vehicle_id=%s",
        command.command,
        command.vehicle_id,
    )

    method_name = _COMMAND_HANDLERS.get(command.command)
    if method_name is None:
        raise ValueError(f"Unsupported worker command: {command.command}")

    config = TeslaConfig.from_env()
    with create_fleet_client(command.access_token, config) as client:
        service = VehicleService(client)
        result = getattr(service, method_name)(command.vehicle_id)

    if not result.success:
        raise RuntimeError(
            f"Worker command failed: command={command.command} "
            f"vehicle_id={command.vehicle_id} reason={result.reason}"
        )

    logger.info(
        "Worker command succeeded: command=%s vehicle_id=%s",
        command.command,
        command.vehicle_id,
    )
    return {"success": True, "reason": result.reason}
