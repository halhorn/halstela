"""halstela.alexa.lwa のテスト"""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from halstela.alexa.lwa import LwaClient, LwaError, LwaTokens, SsmLwaTokenStore


class TestLwaClient:
    def test_exchange_code(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "access_token": "at",
                    "refresh_token": "rt",
                    "token_type": "bearer",
                    "expires_in": 3600,
                },
            )
        )
        http = httpx.Client(transport=transport)
        client = LwaClient("cid", "secret", http)
        tokens = client.exchange_code("auth-code")
        assert tokens == LwaTokens(access_token="at", refresh_token="rt")

    def test_refresh_keeps_refresh_token_if_omitted(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"access_token": "at2", "token_type": "bearer", "expires_in": 3600}
            )
        )
        http = httpx.Client(transport=transport)
        client = LwaClient("cid", "secret", http)
        tokens = client.refresh("rt")
        assert tokens.access_token == "at2"
        assert tokens.refresh_token == "rt"

    def test_http_error_raises_lwa_error(self) -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(400, text="bad"))
        http = httpx.Client(transport=transport)
        client = LwaClient("cid", "secret", http)
        with pytest.raises(LwaError, match="400"):
            client.exchange_code("auth-code")


class TestSsmLwaTokenStore:
    def test_save_and_load(self) -> None:
        ssm = MagicMock()
        ssm.get_parameter.return_value = {
            "Parameter": {
                "Value": json.dumps({"access_token": "at", "refresh_token": "rt"}),
            }
        }
        store = SsmLwaTokenStore("/halstela", ssm)
        store.save(LwaTokens(access_token="at", refresh_token="rt"))
        ssm.put_parameter.assert_called_once()
        kwargs = ssm.put_parameter.call_args.kwargs
        assert kwargs["Name"] == "/halstela/alexa-event-gateway-tokens"
        assert kwargs["Type"] == "SecureString"
        assert json.loads(kwargs["Value"]) == {"access_token": "at", "refresh_token": "rt"}
        assert store.load() == LwaTokens(access_token="at", refresh_token="rt")

    def test_load_missing_returns_none(self) -> None:
        class ParameterNotFound(Exception):
            pass

        ssm = MagicMock()
        ssm.get_parameter.side_effect = ParameterNotFound()
        store = SsmLwaTokenStore("/halstela", ssm)
        assert store.load() is None
