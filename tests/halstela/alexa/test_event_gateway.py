"""halstela.alexa.event_gateway のテスト"""

import json

import httpx
import pytest

from halstela.alexa.event_gateway import EventGatewayClient, EventGatewayError
from halstela.alexa.properties import connectivity_ok_property, power_state_property


class TestEventGatewayClient:
    def test_send_change_report_posts_expected_body(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers["Authorization"]
            captured["body"] = json.loads(request.content)
            return httpx.Response(202)

        http = httpx.Client(transport=httpx.MockTransport(handler))
        client = EventGatewayClient("https://api.fe.amazonalexa.com/v3/events", http)
        changed = [power_state_property("ON", "2026-01-01T00:00:00+00:00")]
        context = [connectivity_ok_property("2026-01-01T00:00:00+00:00")]
        client.send_change_report("lwa-token", "VIN1", changed, context)

        assert captured["url"] == "https://api.fe.amazonalexa.com/v3/events"
        assert captured["authorization"] == "Bearer lwa-token"
        event = captured["body"]["event"]
        assert event["header"]["name"] == "ChangeReport"
        assert event["endpoint"]["endpointId"] == "VIN1"
        assert event["endpoint"]["scope"]["token"] == "lwa-token"
        assert event["payload"]["change"]["cause"]["type"] == "VOICE_INTERACTION"
        assert event["payload"]["change"]["properties"] == changed
        assert captured["body"]["context"]["properties"] == context

    def test_non_202_raises(self) -> None:
        http = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(401, text="no")))
        client = EventGatewayClient("https://example.com/v3/events", http)
        with pytest.raises(EventGatewayError) as exc:
            client.send_change_report("tok", "VIN1", [], [])
        assert exc.value.status_code == 401
