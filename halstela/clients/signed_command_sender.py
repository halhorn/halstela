"""Vehicle Command Protocol による署名付きコマンド送信。"""

import asyncio
from typing import Any, cast

import aiohttp
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from tesla_fleet_api import TeslaFleetApi


class SignedCommandSender:
    """tesla-fleet-api ライブラリを使った署名付きコマンド送信。

    CommandSender Protocol を満たす。
    """

    _COMMAND_DISPATCH: dict[str, str] = {
        "auto_conditioning_start": "auto_conditioning_start",
        "auto_conditioning_stop": "auto_conditioning_stop",
    }

    def __init__(
        self,
        access_token: str,
        private_key_pem: str,
        base_url: str = "https://fleet-api.prd.na.vn.cloud.tesla.com",
    ) -> None:
        self._access_token = access_token
        self._private_key = self._load_private_key(private_key_pem)
        self._base_url = base_url

    def send_command(
        self, vehicle_id: str, command: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        method_name = self._COMMAND_DISPATCH.get(command)
        if method_name is None:
            raise NotImplementedError(f"Signed command not supported: {command}")
        return asyncio.run(self._send_signed(vehicle_id, method_name))

    async def _send_signed(self, vin: str, method_name: str) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            api = TeslaFleetApi(
                session=session,
                access_token=self._access_token,
                server=self._base_url,
            )
            api.private_key = self._private_key
            vehicle = api.vehicles.createSigned(vin)
            method = getattr(vehicle, method_name)
            result: dict[str, Any] = await method()
            return cast(dict[str, Any], result.get("response", {}))

    @staticmethod
    def _load_private_key(pem: str) -> ec.EllipticCurvePrivateKey:
        key = load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey):
            raise ValueError("Private key must be an EC key (SECP256R1)")
        return key
