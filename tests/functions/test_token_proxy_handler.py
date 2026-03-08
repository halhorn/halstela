"""functions/token_proxy/handler.py のテスト"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

from functions.token_proxy.handler import (
    _parse_body,
    lambda_handler,
    proxy_token_request,
)


class TestParseBody:
    def test_plain_body(self) -> None:
        event = {"body": "grant_type=authorization_code&code=abc123", "isBase64Encoded": False}
        result = _parse_body(event)
        assert result == {"grant_type": "authorization_code", "code": "abc123"}

    def test_base64_encoded_body(self) -> None:
        raw = "grant_type=refresh_token&refresh_token=xyz"
        event = {"body": base64.b64encode(raw.encode()).decode(), "isBase64Encoded": True}
        result = _parse_body(event)
        assert result == {"grant_type": "refresh_token", "refresh_token": "xyz"}

    def test_empty_body(self) -> None:
        event = {"body": ""}
        result = _parse_body(event)
        assert result == {}


class TestProxyTokenRequest:
    @patch("functions.token_proxy.handler.httpx.Client")
    def test_adds_audience_and_forwards(self, mock_client_cls: MagicMock) -> None:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        params = {
            "grant_type": "authorization_code",
            "code": "auth-code",
            "client_id": "id",
            "client_secret": "secret",
            "redirect_uri": "https://example.com/callback",
        }

        result = proxy_token_request(params)

        assert result["access_token"] == "new-token"
        assert params["audience"] == "https://fleet-api.prd.na.vn.cloud.tesla.com"

        call_kwargs = mock_client.post.call_args
        assert "audience" in call_kwargs.kwargs.get(
            "content", call_kwargs.args[1] if len(call_kwargs.args) > 1 else ""
        )


class TestLambdaHandler:
    @patch("functions.token_proxy.handler.proxy_token_request")
    def test_success(self, mock_proxy: MagicMock) -> None:
        mock_proxy.return_value = {"access_token": "tok", "expires_in": 3600}

        event = {
            "body": "grant_type=authorization_code&code=abc",
            "isBase64Encoded": False,
        }
        result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["access_token"] == "tok"

    @patch("functions.token_proxy.handler.proxy_token_request")
    def test_proxy_error(self, mock_proxy: MagicMock) -> None:
        mock_proxy.side_effect = RuntimeError("connection failed")

        event = {"body": "grant_type=authorization_code&code=abc", "isBase64Encoded": False}
        result = lambda_handler(event, None)

        assert result["statusCode"] == 500
