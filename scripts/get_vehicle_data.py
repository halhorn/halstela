#!/usr/bin/env -S uv run python
"""Tesla Fleet API から vehicle_data を取得して JSON 出力する。"""

import json
import os
import sys

from halstela.auth.token import TokenManager
from halstela.clients.tesla_fleet_client import TeslaFleetClient
from halstela.config import TeslaConfig


def main() -> int:
    try:
        config = TeslaConfig.from_env()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        token = _get_access_token(config)

        with TeslaFleetClient(token, config.fleet_api_base_url) as client:
            from halstela.services.vehicle_service import VehicleService

            service = VehicleService(client)
            vehicles = service.get_vehicles()

            target_vin = os.getenv("TESLA_TARGET_VIN")
            vehicle = _select_vehicle(vehicles, target_vin)

            data = service.get_vehicle_data(vehicle.vin)

            result = {
                "vehicle": {
                    "display_name": vehicle.display_name,
                    "vin": vehicle.vin,
                    "state": vehicle.state,
                },
                "vehicle_data": data,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
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
