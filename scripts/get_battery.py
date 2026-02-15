#!/usr/bin/env -S uv run python
"""
Tesla Fleet API からバッテリー残量を取得する最小スクリプト（httpx使用版）。
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse

from halstela.config import TeslaConfig
from halstela.http_client import TeslaHTTPClient
from halstela.token import TokenManager


def _get_access_token(config: TeslaConfig) -> str:
    """アクセストークンを取得"""
    token = os.getenv("TESLA_ACCESS_TOKEN")
    if token:
        return token

    token_manager = TokenManager(config.get_token_file_path())
    return token_manager.get_access_token()


def _list_vehicles(http_client: TeslaHTTPClient, token: str) -> list[dict]:
    """車両一覧を取得"""
    payload = http_client.get_json("/api/1/vehicles", token)
    vehicles = payload.get("response")
    if not isinstance(vehicles, list) or not vehicles:
        raise RuntimeError(f"車両一覧が取得できませんでした: {json.dumps(payload, ensure_ascii=False)}")
    return vehicles


def _select_vehicle(vehicles: list[dict]) -> dict:
    """車両を選択"""
    target_vin = os.getenv("TESLA_TARGET_VIN")
    if target_vin:
        for v in vehicles:
            if v.get("vin") == target_vin:
                return v
        raise RuntimeError(f"TESLA_TARGET_VIN={target_vin} に一致する車両が見つかりません。")
    return vehicles[0]


def _vehicle_identifier(vehicle: dict) -> str:
    """車両識別子を取得"""
    if vehicle.get("id_s"):
        return str(vehicle["id_s"])
    if vehicle.get("id"):
        return str(vehicle["id"])
    raise RuntimeError(f"車両識別子が見つかりません: {json.dumps(vehicle, ensure_ascii=False)}")


def _get_charge_state(http_client: TeslaHTTPClient, token: str, vehicle_id: str) -> dict:
    """充電状態を取得"""
    # Fleet API 形式
    paths = [
        f"/api/1/vehicles/{urllib.parse.quote(vehicle_id)}/vehicle_data?endpoints=charge_state",
        # 互換用途 (環境差異対策)
        f"/api/1/vehicles/{urllib.parse.quote(vehicle_id)}/data_request/charge_state",
    ]

    last_error: Exception | None = None
    for path in paths:
        try:
            payload = http_client.get_json(path, token)
            response = payload.get("response", {})
            charge_state = response.get("charge_state", response)
            if isinstance(charge_state, dict) and charge_state.get("battery_level") is not None:
                return charge_state
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    if last_error:
        raise RuntimeError(f"charge_state の取得に失敗しました: {last_error}") from last_error
    raise RuntimeError("charge_state の取得に失敗しました。")


def main() -> int:
    """メイン関数"""
    description = """Tesla Fleet API からバッテリー残量を取得

使用方法:
  %(prog)s

環境変数:
  - TESLA_ACCESS_TOKEN: アクセストークン（未指定時は secret/token.json から読み込み）
  - TESLA_TARGET_VIN: 対象車両のVIN（未指定時は最初の車両を使用）
"""
    import argparse

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args()

    # 設定読み込み
    try:
        config = TeslaConfig()
    except Exception as exc:
        print(f"[ERROR] 設定の読み込みに失敗しました: {exc}", file=sys.stderr)
        return 1

    try:
        token = _get_access_token(config)

        with TeslaHTTPClient(config.api_base_url) as http_client:
            vehicles = _list_vehicles(http_client, token)
            vehicle = _select_vehicle(vehicles)
            vehicle_id = _vehicle_identifier(vehicle)
            charge_state = _get_charge_state(http_client, token, vehicle_id)

            result = {
                "vehicle_display_name": vehicle.get("display_name"),
                "vin": vehicle.get("vin"),
                "battery_level": charge_state.get("battery_level"),
                "usable_battery_level": charge_state.get("usable_battery_level"),
                "charging_state": charge_state.get("charging_state"),
                "timestamp": charge_state.get("timestamp"),
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
