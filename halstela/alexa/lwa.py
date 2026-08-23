"""Login with Amazon で Event Gateway 用トークンを取得・保存する。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
_TOKENS_PARAM = "alexa-event-gateway-tokens"
_CLIENT_ID_PARAM = "alexa-lwa-client-id"
_CLIENT_SECRET_PARAM = "alexa-lwa-client-secret"


@dataclass(frozen=True)
class LwaTokens:
    access_token: str
    refresh_token: str


class LwaError(Exception):
    """LWA トークンエンドポイントのエラー。"""


class LwaTokenStore(Protocol):
    """Event Gateway 用 LWA トークンの永続化。"""

    def save(self, tokens: LwaTokens) -> None: ...

    def load(self) -> LwaTokens | None: ...


class LwaClient:
    """LWA の authorization_code / refresh_token 交換。"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = http_client or httpx.Client(timeout=10.0)
        self._owns_http = http_client is None

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> LwaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @classmethod
    def from_env(cls) -> LwaClient:
        ssm_prefix = os.environ.get("SSM_PREFIX")
        if ssm_prefix:
            params = _get_ssm_parameters(
                [f"{ssm_prefix}/{_CLIENT_ID_PARAM}", f"{ssm_prefix}/{_CLIENT_SECRET_PARAM}"]
            )
            client_id = params.get(_CLIENT_ID_PARAM, "")
            client_secret = params.get(_CLIENT_SECRET_PARAM, "")
        else:
            client_id = os.environ.get("ALEXA_LWA_CLIENT_ID", "")
            client_secret = os.environ.get("ALEXA_LWA_CLIENT_SECRET", "")
        if not client_id or not client_secret:
            raise LwaError("Alexa LWA client_id/client_secret is not configured")
        return cls(client_id, client_secret)

    def exchange_code(self, code: str) -> LwaTokens:
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        )

    def refresh(self, refresh_token: str) -> LwaTokens:
        return self._token_request(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            }
        )

    def _token_request(self, data: dict[str, str]) -> LwaTokens:
        try:
            response = self._http.post(
                LWA_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LwaError(
                f"LWA token request failed: {exc.response.status_code} {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise LwaError(f"LWA token request failed: {exc}") from exc
        body: dict[str, Any] = response.json()
        return LwaTokens(
            access_token=str(body["access_token"]),
            refresh_token=str(body.get("refresh_token") or data.get("refresh_token", "")),
        )


class SsmLwaTokenStore:
    """Event Gateway 用 LWA トークンを SSM に 1 ユーザー分保存する。"""

    def __init__(self, prefix: str, ssm_client: Any | None = None) -> None:
        self._param_name = f"{prefix}/{_TOKENS_PARAM}"
        if ssm_client is None:
            import boto3

            ssm_client = boto3.client("ssm")
        self._ssm = ssm_client

    @classmethod
    def from_env(cls) -> SsmLwaTokenStore:
        prefix = os.environ.get("SSM_PREFIX", "/halstela")
        return cls(prefix)

    def save(self, tokens: LwaTokens) -> None:
        self._ssm.put_parameter(
            Name=self._param_name,
            Type="SecureString",
            Value=json.dumps(
                {"access_token": tokens.access_token, "refresh_token": tokens.refresh_token}
            ),
            Overwrite=True,
        )

    def load(self) -> LwaTokens | None:
        try:
            resp = self._ssm.get_parameter(Name=self._param_name, WithDecryption=True)
        except Exception as exc:
            if exc.__class__.__name__ == "ParameterNotFound":
                return None
            raise
        raw = json.loads(resp["Parameter"]["Value"])
        return LwaTokens(access_token=raw["access_token"], refresh_token=raw["refresh_token"])


def _get_ssm_parameters(names: list[str]) -> dict[str, str]:
    import boto3

    ssm = boto3.client("ssm")
    resp = ssm.get_parameters(Names=names, WithDecryption=True)
    return {p["Name"].rsplit("/", 1)[-1]: p["Value"] for p in resp["Parameters"]}
