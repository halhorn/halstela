#!/usr/bin/env -S uv run python
"""
Tesla Fleet API から vehicle_data を取得し、すべての結果を見やすく出力する。
"""

from __future__ import annotations

import json
import os
import sys
import time
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
        raise RuntimeError(
            f"車両一覧が取得できませんでした: {json.dumps(payload, ensure_ascii=False)}"
        )
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


def _wake_up(http_client: TeslaHTTPClient, token: str, vin: str) -> None:
    """車両をスリープから起こす"""
    path = f"/api/1/vehicles/{urllib.parse.quote(vin)}/wake_up"
    http_client.post_json(path, token, {})


def _wait_until_online(
    http_client: TeslaHTTPClient, token: str, vin: str, timeout: float = 60.0
) -> None:
    """車両がオンラインになるまで待つ"""
    path = f"/api/1/vehicles/{urllib.parse.quote(vin)}"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = http_client.get_json(path, token)
        state = payload.get("response", {}).get("state")
        if state == "online":
            return
        time.sleep(3)
    raise RuntimeError(f"車両がオンラインになりませんでした（{timeout}秒以内）")


def _get_vehicle_data(http_client: TeslaHTTPClient, token: str, vin: str) -> dict:
    """vehicle_data を取得"""
    path = f"/api/1/vehicles/{urllib.parse.quote(vin)}/vehicle_data"
    payload = http_client.get_json(path, token)
    response = payload.get("response", {})
    if not isinstance(response, dict):
        raise RuntimeError(
            f"vehicle_data の取得に失敗しました: response={json.dumps(response, ensure_ascii=False)[:500]}"
        )
    return response


def main() -> int:
    """メイン関数"""
    description = """Tesla Fleet API から vehicle_data を取得

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

        with TeslaHTTPClient(config.api_base_url, timeout=30.0) as http_client:
            vehicles = _list_vehicles(http_client, token)
            vehicle = _select_vehicle(vehicles)
            vin = vehicle["vin"]
            try:
                vehicle_data = _get_vehicle_data(http_client, token, vin)
            except RuntimeError as exc:
                if "408" not in str(exc):
                    raise
                print("車両がスリープ中のため、起こしてから再試行します...", file=sys.stderr)
                _wake_up(http_client, token, vin)
                _wait_until_online(http_client, token, vin)
                vehicle_data = _get_vehicle_data(http_client, token, vin)

            result = {
                "vehicle": {
                    "display_name": vehicle.get("display_name"),
                    "vin": vehicle.get("vin"),
                },
                "vehicle_data": vehicle_data,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
