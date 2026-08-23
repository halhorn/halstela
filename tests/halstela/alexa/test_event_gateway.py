"""halstela.alexa.event_gateway のテスト"""

import json
from unittest.mock import MagicMock

import httpx
import pytest

from halstela.alexa.event_gateway import EventGatewayClient, EventGatewayError
from halstela.alexa.lwa import LwaTokens
from halstela.alexa.properties import connectivity_ok_property, power_state_property


def _client(
    http: httpx.Client,
    store: MagicMock | None = None,
    lwa: MagicMock | None = None,
    url: str = "https://api.fe.amazonalexa.com/v3/events",
) -> EventGatewayClient:
    if store is None:
        store = MagicMock()
        store.load.return_value = LwaTokens(access_token="lwa-token", refresh_token="rt")
    if lwa is None:
        lwa = MagicMock()
    return EventGatewayClient(url, token_store=store, lwa_client=lwa, http_client=http)


class TestEventGatewayClient:
    def test_send_change_report_posts_expected_body(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers["Authorization"]
            captured["body"] = json.loads(request.content)
            return httpx.Response(202)

        changed = [power_state_property("ON", "2026-01-01T00:00:00+00:00")]
        context = [connectivity_ok_property("2026-01-01T00:00:00+00:00")]
        _client(httpx.Client(transport=httpx.MockTransport(handler))).send_change_report(
            "VIN1", changed, context
        )

        assert captured["url"] == "https://api.fe.amazonalexa.com/v3/events"
        assert captured["authorization"] == "Bearer lwa-token"
        event = captured["body"]["event"]
        assert event["header"]["name"] == "ChangeReport"
        assert event["endpoint"]["endpointId"] == "VIN1"
        assert event["endpoint"]["scope"]["token"] == "lwa-token"
        assert event["payload"]["change"]["cause"]["type"] == "VOICE_INTERACTION"
        assert event["payload"]["change"]["properties"] == [p.to_dict() for p in changed]
        assert captured["body"]["context"]["properties"] == [p.to_dict() for p in context]

    def test_non_202_raises(self) -> None:
        http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(500, text="no")))
        with pytest.raises(EventGatewayError) as exc:
            _client(http, url="https://example.com/v3/events").send_change_report("VIN1", [], [])
        assert exc.value.status_code == 500

    def test_missing_tokens_raises(self) -> None:
        store = MagicMock()
        store.load.return_value = None
        http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(202)))
        with pytest.raises(EventGatewayError, match="LWA tokens are not stored"):
            _client(http, store=store).send_change_report("VIN1", [], [])

    def test_401_refreshes_token_and_retries(self) -> None:
        statuses = iter([401, 202])
        tokens_used: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            tokens_used.append(request.headers["Authorization"])
            return httpx.Response(next(statuses), text="expired")

        store = MagicMock()
        store.load.return_value = LwaTokens(access_token="old", refresh_token="rt")
        lwa = MagicMock()
        lwa.refresh.return_value = LwaTokens(access_token="new", refresh_token="rt2")
        _client(
            httpx.Client(transport=httpx.MockTransport(handler)), store=store, lwa=lwa
        ).send_change_report("VIN1", [], [])

        lwa.refresh.assert_called_once_with("rt")
        store.save.assert_called_once_with(LwaTokens(access_token="new", refresh_token="rt2"))
        assert tokens_used == ["Bearer old", "Bearer new"]

    def test_accept_grant_exchanges_code_and_saves(self) -> None:
        store = MagicMock()
        lwa = MagicMock()
        lwa.exchange_code.return_value = LwaTokens(access_token="at", refresh_token="rt")
        http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(202)))
        _client(http, store=store, lwa=lwa).accept_grant("auth-code")

        lwa.exchange_code.assert_called_once_with("auth-code")
        store.save.assert_called_once_with(LwaTokens(access_token="at", refresh_token="rt"))
