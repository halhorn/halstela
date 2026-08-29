"""Command Worker Lambda ハンドラー

Skill Lambda から非同期に起動され、Tesla へのコマンド実行を担う。
コマンド成否に関わらず、取得できた現在状態を Alexa Event Gateway へ ChangeReport する（ベストエフォート）。
"""

from __future__ import annotations

import logging
from typing import Any

from halstela.alexa.event_gateway import EventGatewayClient
from halstela.alexa.properties import (
    climate_context_property,
    connectivity_ok_property,
    power_state_from_climate,
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
            _send_change_report(service=service, vehicle_id=command.vehicle_id)
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
    if command.command == "auto_conditioning_stop":
        return service.auto_conditioning_stop(command.vehicle_id)
    raise ValueError(f"Unsupported worker command: {command.command}")


def _send_change_report(service: VehicleService, vehicle_id: str) -> None:
    try:
        climate = service.get_climate_state(vehicle_id)
        with _create_event_gateway_client() as gateway:
            gateway.send_change_report(
                endpoint_id=vehicle_id,
                changed=[power_state_from_climate(climate=climate)],
                context=[
                    climate_context_property(climate=climate),
                    connectivity_ok_property(),
                ],
            )
        logger.info(f"ChangeReport sent: vehicle_id={vehicle_id}")
    except Exception as exc:
        logger.exception(f"ChangeReport failed: {exc!r}")


def _create_event_gateway_client() -> EventGatewayClient:
    return EventGatewayClient.from_env()
