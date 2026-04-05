#!/usr/bin/env -S uv run python
"""Tesla Fleet API でエアコンを起動するデバッグスクリプト。"""

import os
import sys

from halstela.auth.token import TokenManager
from halstela.clients.tesla_fleet_client import TeslaFleetClient
from halstela.config import TeslaConfig
from halstela.services.vehicle_service import VehicleService


def main() -> int:
    try:
        config = TeslaConfig.from_env()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        token = _get_access_token(config)

        with TeslaFleetClient(token, config.fleet_api_base_url) as client:
            service = VehicleService(client)
            vehicles = service.get_vehicles()

            target_vin = os.getenv("TESLA_TARGET_VIN")
            vehicle = _select_vehicle(vehicles, target_vin)
            print(f"対象車両: {vehicle.display_name} ({vehicle.vin})")

            print("エアコンを起動しています...")
            result = service.start_air_conditioning(vehicle.vin)

            if result.success:
                print("エアコンを起動しました。")
            else:
                print(f"[ERROR] エアコンの起動に失敗しました: {result.reason}", file=sys.stderr)
                return 1
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _get_access_token(config: TeslaConfig) -> str:
    token = os.getenv("TESLA_ACCESS_TOKEN")
    if token:
        return token
    token_manager = TokenManager(config.get_token_file_path())
    return token_manager.get_access_token()


def _select_vehicle(vehicles: list, target_vin: str | None) -> object:
    if target_vin:
        for v in vehicles:
            if v.vin == target_vin:
                return v
        raise RuntimeError(f"TESLA_TARGET_VIN={target_vin} に一致する車両が見つかりません。")
    if not vehicles:
        raise RuntimeError("車両が見つかりません。")
    return vehicles[0]


if __name__ == "__main__":
    raise SystemExit(main())
