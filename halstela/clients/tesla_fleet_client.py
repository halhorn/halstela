"""Tesla Fleet API クライアント（Client 層）"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

import httpx

if TYPE_CHECKING:
    from halstela.config import TeslaConfig


class TeslaAPIError(Exception):
    """Tesla API 呼び出し時のエラー"""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class CommandSender(Protocol):
    """車両コマンド送信の抽象インターフェース。"""

    def send_command(
        self, vehicle_id: str, command: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...


class RestCommandSender:
    """従来の REST API によるコマンド送信。"""

    def __init__(self, http_client: httpx.Client) -> None:
        self._client = http_client

    def send_command(
        self, vehicle_id: str, command: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.post(
                f"/api/1/vehicles/{vehicle_id}/command/{command}",
                json=body or {},
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return cast(dict[str, Any], data.get("response", {}))
        except httpx.HTTPStatusError as exc:
            raise TeslaAPIError(exc.response.status_code, exc.response.text) from exc


class TeslaFleetClient:
    """Tesla Fleet API との HTTP 通信を担当する低レベルクライアント。

    access_token ごとにインスタンスを生成する想定。
    """

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://fleet-api.prd.na.vn.cloud.tesla.com",
        timeout: float = 30.0,
        command_sender: CommandSender | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._command_sender = command_sender or RestCommandSender(self._client)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TeslaFleetClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_vehicles(self) -> list[dict[str, Any]]:
        data = self._get("/api/1/vehicles")
        vehicles = data.get("response", [])
        if not isinstance(vehicles, list):
            raise TeslaAPIError(0, f"Unexpected response format: {data}")
        return vehicles

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any]:
        data = self._get(f"/api/1/vehicles/{vehicle_id}")
        return cast(dict[str, Any], data.get("response", {}))

    def get_vehicle_data(
        self, vehicle_id: str, endpoints: list[str] | None = None
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if endpoints:
            params["endpoints"] = ";".join(endpoints)
        data = self._get(f"/api/1/vehicles/{vehicle_id}/vehicle_data", params=params)
        return cast(dict[str, Any], data.get("response", {}))

    def send_command(
        self, vehicle_id: str, command: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._command_sender.send_command(vehicle_id, command, body)

    def wake_up(self, vehicle_id: str) -> dict[str, Any]:
        data = self._post(f"/api/1/vehicles/{vehicle_id}/wake_up", json={})
        return cast(dict[str, Any], data.get("response", {}))

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            response = self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as exc:
            raise TeslaAPIError(exc.response.status_code, exc.response.text) from exc

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=json)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as exc:
            raise TeslaAPIError(exc.response.status_code, exc.response.text) from exc


def create_fleet_client(access_token: str, config: TeslaConfig) -> TeslaFleetClient:
    """TeslaConfig から適切な CommandSender を選択して TeslaFleetClient を生成する。"""
    command_sender: CommandSender | None = None
    if config.private_key_pem:
        from halstela.clients.signed_command_sender import SignedCommandSender

        command_sender = SignedCommandSender(
            access_token=access_token,
            private_key_pem=config.private_key_pem,
            base_url=config.fleet_api_base_url,
        )
    return TeslaFleetClient(
        access_token=access_token,
        base_url=config.fleet_api_base_url,
        command_sender=command_sender,
    )
