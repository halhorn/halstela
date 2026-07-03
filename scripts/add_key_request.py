#!/usr/bin/env -S uv run python
"""車両にアプリの公開鍵ペアリングリクエストを送信するスクリプト。

車両のタッチスクリーンで「コントロール → ロック → 鍵」を開いた状態で実行する。
タッチスクリーンに承認プロンプトが表示されるので「承認」をタップする。
"""

import base64
import os
import sys

import httpx
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

from tesla_fleet_api.tesla.vehicle.proto.keys_pb2 import ROLE_OWNER
from tesla_fleet_api.tesla.vehicle.proto.universal_message_pb2 import (
    DOMAIN_VEHICLE_SECURITY,
    Destination,
    RoutableMessage,
)
from tesla_fleet_api.tesla.vehicle.proto.vcsec_pb2 import (
    KEY_FORM_FACTOR_CLOUD_KEY,
    KeyMetadata,
    PermissionChange,
    PublicKey,
    UnsignedMessage,
    WhitelistOperation,
)

from halstela.auth.token import TokenManager
from halstela.config import TeslaConfig
from halstela.services.vehicle_service import VehicleService
from halstela.clients.tesla_fleet_client import TeslaFleetClient


def main() -> int:
    try:
        config = TeslaConfig.from_env()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if not config.private_key_pem:
        print("[ERROR] 秘密鍵が見つかりません (secret/private.pem)", file=sys.stderr)
        return 1

    try:
        token = _get_access_token(config)
        public_key_bytes = _get_public_key_bytes(config.private_key_pem)

        with TeslaFleetClient(token, config.fleet_api_base_url) as client:
            service = VehicleService(client)
            vehicles = service.get_vehicles()
            target_vin = os.getenv("TESLA_TARGET_VIN")
            vehicle = _select_vehicle(vehicles, target_vin)
            print(f"対象車両: {vehicle.display_name} ({vehicle.vin})")

            print()
            print("車両のタッチスクリーンで「コントロール → ロック → 鍵」を開いてください。")
            input("準備ができたら Enter を押してください...")

            print("車両を起動しています...")
            service.ensure_awake(vehicle.vin)
            print("車両がオンラインです。")

            print("キーペアリングリクエストを送信しています...")
            _send_add_key_request(
                access_token=token,
                base_url=config.fleet_api_base_url,
                vin=vehicle.vin,
                public_key_bytes=public_key_bytes,
            )
            print("リクエストを送信しました。")
            print("車両のタッチスクリーンに承認プロンプトが表示されます。「承認」をタップしてください。")

        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _send_add_key_request(
    access_token: str,
    base_url: str,
    vin: str,
    public_key_bytes: bytes,
) -> None:
    """Fleet API 経由でキーペアリングリクエストを送信する。"""
    unsigned_msg = UnsignedMessage(
        WhitelistOperation=WhitelistOperation(
            addKeyToWhitelistAndAddPermissions=PermissionChange(
                key=PublicKey(PublicKeyRaw=public_key_bytes),
                keyRole=ROLE_OWNER,
            ),
            metadataForKey=KeyMetadata(keyFormFactor=KEY_FORM_FACTOR_CLOUD_KEY),
        ),
    )

    routable_msg = RoutableMessage(
        to_destination=Destination(domain=DOMAIN_VEHICLE_SECURITY),
        protobuf_message_as_bytes=unsigned_msg.SerializeToString(),
    )

    payload = base64.b64encode(routable_msg.SerializeToString()).decode()

    with httpx.Client(
        base_url=base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    ) as client:
        response = client.post(
            f"/api/1/vehicles/{vin}/signed_command",
            json={"routable_message": payload},
        )
        if not response.is_success:
            print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
            response.raise_for_status()


def _get_public_key_bytes(private_key_pem: str) -> bytes:
    """秘密鍵から公開鍵の非圧縮バイト列を取得する。"""
    key = load_pem_private_key(private_key_pem.encode(), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("秘密鍵が EC 鍵ではありません")
    return key.public_key().public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint
    )


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
