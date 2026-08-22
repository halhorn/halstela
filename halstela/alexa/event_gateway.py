"""Alexa Event Gateway へ ChangeReport を送るクライアント。"""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx

DEFAULT_GATEWAY_URL = "https://api.fe.amazonalexa.com/v3/events"


class EventGatewayError(Exception):
    """Event Gateway がイベントを受理しなかった。"""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class EventGatewayClient:
    """ChangeReport を Event Gateway に POST する。"""

    def __init__(
        self,
        gateway_url: str = DEFAULT_GATEWAY_URL,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._gateway_url = gateway_url
        self._http = http_client or httpx.Client(timeout=10.0)
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> EventGatewayClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @classmethod
    def from_env(cls) -> EventGatewayClient:
        return cls(os.environ.get("ALEXA_EVENT_GATEWAY_URL", DEFAULT_GATEWAY_URL))

    def send_change_report(
        self,
        access_token: str,
        endpoint_id: str,
        changed_properties: list[dict[str, Any]],
        context_properties: list[dict[str, Any]],
        cause: str = "VOICE_INTERACTION",
    ) -> None:
        body = {
            "event": {
                "header": {
                    "namespace": "Alexa",
                    "name": "ChangeReport",
                    "messageId": str(uuid.uuid4()),
                    "payloadVersion": "3",
                },
                "endpoint": {
                    "scope": {"type": "BearerToken", "token": access_token},
                    "endpointId": endpoint_id,
                },
                "payload": {
                    "change": {
                        "cause": {"type": cause},
                        "properties": changed_properties,
                    }
                },
            },
            "context": {"properties": context_properties},
        }
        try:
            response = self._http.post(
                self._gateway_url,
                json=body,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            raise EventGatewayError(0, str(exc)) from exc
        if response.status_code != 202:
            raise EventGatewayError(response.status_code, response.text)
