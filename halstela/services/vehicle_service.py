"""車両操作ビジネスロジック（Service 層）"""

from __future__ import annotations

import logging
import time
from typing import Any

from halstela.clients.tesla_fleet_client import TeslaAPIError, TeslaFleetClient
from halstela.models.climate_state import ClimateState
from halstela.models.command_result import CommandResult
from halstela.models.vehicle import Vehicle

logger = logging.getLogger(__name__)

WAKE_UP_TIMEOUT = 60.0
WAKE_UP_POLL_INTERVAL = 3.0


class VehicleService:
    """Tesla Fleet API を使った車両操作のビジネスロジック。

    wake_up 制御や API レスポンスから dataclass への変換を担う。
    """

    def __init__(self, client: TeslaFleetClient) -> None:
        self._client = client

    def get_vehicles(self) -> list[Vehicle]:
        raw = self._client.get_vehicles()
        return [
            Vehicle(
                id=str(v.get("id_s", v.get("id", ""))),
                vin=v.get("vin", ""),
                display_name=v.get("display_name", ""),
                state=v.get("state", "unknown"),
            )
            for v in raw
        ]

    def get_vehicle_data(
        self, vehicle_id: str, endpoints: list[str] | None = None
    ) -> dict[str, Any]:
        """wake_up してから車両データを取得する。"""
        self.ensure_awake(vehicle_id)
        return self._client.get_vehicle_data(vehicle_id, endpoints=endpoints)

    def get_climate_state(self, vehicle_id: str) -> ClimateState:
        self.ensure_awake(vehicle_id)
        data = self._client.get_vehicle_data(vehicle_id, endpoints=["climate_state"])
        climate = data.get("climate_state", {})
        return ClimateState(
            inside_temp=climate.get("inside_temp"),
            outside_temp=climate.get("outside_temp"),
            is_climate_on=bool(climate.get("is_climate_on", False)),
            driver_temp_setting=float(climate.get("driver_temp_setting", 0.0)),
        )

    def start_air_conditioning(self, vehicle_id: str) -> CommandResult:
        self.ensure_awake(vehicle_id)
        result = self._client.send_command(vehicle_id, "auto_conditioning_start")
        return CommandResult(
            success=bool(result.get("result", False)),
            reason=str(result.get("reason", "")),
        )

    def ensure_awake(
        self,
        vehicle_id: str,
        timeout: float = WAKE_UP_TIMEOUT,
    ) -> None:
        """車両がオンラインでなければ wake_up → ポーリングで待機する。"""
        try:
            vehicle_data = self._client.get_vehicle(vehicle_id)
        except TeslaAPIError as exc:
            if exc.status_code == 408:
                vehicle_data = {"state": "asleep"}
            else:
                raise

        if vehicle_data.get("state") == "online":
            return

        logger.info("Vehicle %s is not online, sending wake_up", vehicle_id)
        self._client.wake_up(vehicle_id)

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(WAKE_UP_POLL_INTERVAL)
            try:
                vehicle_data = self._client.get_vehicle(vehicle_id)
            except TeslaAPIError:
                continue
            if vehicle_data.get("state") == "online":
                logger.info("Vehicle %s is now online", vehicle_id)
                return

        raise TimeoutError(f"Vehicle {vehicle_id} did not come online within {timeout}s")
