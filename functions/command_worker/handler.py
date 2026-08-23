"""Command Worker Lambda ハンドラー

Skill Lambda から非同期に起動され、Tesla へのコマンド実行を担う。
成功後に Alexa Event Gateway へ ChangeReport を送る（ベストエフォート）。
"""

from __future__ import annotations

import logging
from typing import Any

from halstela.alexa.event_gateway import EventGatewayClient
from halstela.alexa.properties import (
    climate_context_property,
    connectivity_ok_property,
    power_state_property,
)
from halstela.clients.tesla_fleet_client import create_fleet_client
from halstela.config import TeslaConfig
from halstela.models.command_result import CommandResult
from halstela.models.worker_command import WorkerCommand
from halstela.services.vehicle_service import VehicleService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        command = WorkerCommand.from_payload(event)
        # access_token を含むためペイロード全体はログしない
        logger.info(
            f"Worker command received: command={command.command} vehicle_id={command.vehicle_id}"
        )

        config = TeslaConfig.from_env()
        with create_fleet_client(command.access_token, config) as client:
            service = VehicleService(client)
            result = _execute(service, command)
            if result.success:
                _send_change_report(service, command)
    except (KeyError, ValueError):
        logger.exception("Invalid worker command")
        raise

    if not result.success:
        raise RuntimeError(
            f"Worker command failed: command={command.command} "
            f"vehicle_id={command.vehicle_id} reason={result.reason}"
        )

    logger.info(
        f"Worker command succeeded: command={command.command} vehicle_id={command.vehicle_id}"
    )
    return {"success": True, "reason": result.reason}


def _execute(service: VehicleService, command: WorkerCommand) -> CommandResult:
    if command.command == "auto_conditioning_start":
        return service.auto_conditioning_start(command.vehicle_id)
    raise ValueError(f"Unsupported worker command: {command.command}")


def _send_change_report(service: VehicleService, command: WorkerCommand) -> None:
    try:
        climate = service.get_climate_state(command.vehicle_id)
        with _create_event_gateway_client() as gateway:
            gateway.send_change_report(
                endpoint_id=command.vehicle_id,
                changed=[power_state_property(state="ON")],
                context=[
                    climate_context_property(climate=climate),
                    connectivity_ok_property(),
                ],
            )
        logger.info(f"ChangeReport sent: vehicle_id={command.vehicle_id}")
    except Exception:
        logger.exception("ChangeReport failed")


def _create_event_gateway_client() -> EventGatewayClient:
    return EventGatewayClient.from_env()
