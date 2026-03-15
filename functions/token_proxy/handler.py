"""Token Proxy Lambda ハンドラー

Alexa Account Linking のトークン交換を中継し、Tesla が必要とする
audience パラメータを付与する。
"""

import base64
import json
import logging
import os
from typing import Any
from urllib.parse import parse_qs, urlencode

import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TESLA_TOKEN_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
TESLA_AUDIENCE = "https://fleet-api.prd.na.vn.cloud.tesla.com"


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info("Token proxy request received")

    try:
        body = _parse_body(event)
        result = proxy_token_request(body)
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(result),
        }
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Tesla token endpoint error: %d %s",
            exc.response.status_code,
            exc.response.text,
        )
        return {
            "statusCode": exc.response.status_code,
            "headers": {"Content-Type": "application/json"},
            "body": exc.response.text,
        }
    except Exception:
        logger.exception("Token proxy error")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "internal_error"}),
        }


def proxy_token_request(params: dict[str, str]) -> dict[str, Any]:
    """audience を付与して Tesla Token Endpoint に転送する。"""
    token_url = os.environ.get("TESLA_TOKEN_URL", TESLA_TOKEN_URL)
    audience = os.environ.get("TESLA_AUDIENCE", TESLA_AUDIENCE)

    params["audience"] = audience

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            token_url,
            content=urlencode(params),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]


def _extract_basic_auth(event: dict[str, Any]) -> tuple[str, str] | None:
    """Authorization ヘッダーから Basic 認証の client_id / client_secret を取得する。

    Alexa Account Linking の accessTokenScheme が HTTP_BASIC の場合、
    client_id と client_secret は body ではなく Authorization ヘッダーで送られる。
    """
    headers = event.get("headers", {})
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("basic "):
        return None

    decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
    client_id, _, client_secret = decoded.partition(":")
    return client_id, client_secret


def _parse_body(event: dict[str, Any]) -> dict[str, str]:
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        body = base64.b64decode(body).decode("utf-8")

    parsed = parse_qs(body, keep_blank_values=True)
    params = {k: v[0] for k, v in parsed.items()}

    credentials = _extract_basic_auth(event)
    if credentials:
        params.setdefault("client_id", credentials[0])
        params.setdefault("client_secret", credentials[1])

    return params
