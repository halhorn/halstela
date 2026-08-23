"""Alexa Event Gateway クライアント。

認証（LWA トークンの取得・保存・更新）とイベント発行を担う。
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx

from halstela.alexa.lwa import LwaClient, LwaTokenStore, SsmLwaTokenStore
from halstela.alexa.properties import AlexaProperty, properties_as_dicts

DEFAULT_GATEWAY_URL = "https://api.fe.amazonalexa.com/v3/events"


class EventGatewayError(Exception):
    """Event Gateway がイベントを受理しなかった。"""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class EventGatewayClient:
    """認証情報を管理し、ChangeReport を Event Gateway に送る。"""

    def __init__(
        self,
        gateway_url: str = DEFAULT_GATEWAY_URL,
        *,
        token_store: LwaTokenStore,
        lwa_client: LwaClient,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._gateway_url = gateway_url
        self._store = token_store
        self._lwa = lwa_client
        self._http = http_client or httpx.Client(timeout=10.0)
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()
        self._lwa.close()

    def __enter__(self) -> EventGatewayClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @classmethod
    def from_env(cls) -> EventGatewayClient:
        return cls(
            gateway_url=os.environ.get("ALEXA_EVENT_GATEWAY_URL", DEFAULT_GATEWAY_URL),
            token_store=SsmLwaTokenStore.from_env(),
            lwa_client=LwaClient.from_env(),
        )

    def accept_grant(self, code: str) -> None:
        self._store.save(self._lwa.exchange_code(code))

    def send_change_report(
        self,
        endpoint_id: str,
        changed: list[AlexaProperty],
        context: list[AlexaProperty],
        cause: str = "VOICE_INTERACTION",
    ) -> None:
        tokens = self._store.load()
        if tokens is None:
            raise EventGatewayError(0, "LWA tokens are not stored")
        try:
            self._post(
                access_token=tokens.access_token,
                endpoint_id=endpoint_id,
                changed=changed,
                context=context,
                cause=cause,
            )
            return
        except EventGatewayError as exc:
            if exc.status_code != 401:
                raise
        tokens = self._lwa.refresh(refresh_token=tokens.refresh_token)
        self._store.save(tokens)
        self._post(
            access_token=tokens.access_token,
            endpoint_id=endpoint_id,
            changed=changed,
            context=context,
            cause=cause,
        )

    def _post(
        self,
        access_token: str,
        endpoint_id: str,
        changed: list[AlexaProperty],
        context: list[AlexaProperty],
        cause: str,
    ) -> None:
        body: dict[str, Any] = {
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
                        "properties": properties_as_dicts(properties=changed),
                    }
                },
            },
            "context": {"properties": properties_as_dicts(properties=context)},
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
