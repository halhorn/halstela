"""Tesla Fleet API クライアント（Client 層）"""

from typing import Any, cast

import httpx


class TeslaAPIError(Exception):
    """Tesla API 呼び出し時のエラー"""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class TeslaFleetClient:
    """Tesla Fleet API との HTTP 通信を担当する低レベルクライアント。

    access_token ごとにインスタンスを生成する想定。
    """

    def __init__(
        self,
        access_token: str,
        base_url: str = "https://fleet-api.prd.na.vn.cloud.tesla.com",
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

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
        data = self._post(f"/api/1/vehicles/{vehicle_id}/command/{command}", json=body or {})
        return cast(dict[str, Any], data.get("response", {}))

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
