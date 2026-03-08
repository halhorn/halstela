"""functions/skill/handler.py のテスト"""

from unittest.mock import MagicMock, patch

import pytest

from functions.skill.handler import (
    _error_response,
    handle_discovery,
    handle_power_control,
    handle_report_state,
    lambda_handler,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESLA_CLIENT_ID", "test-id")
    monkeypatch.setenv("TESLA_CLIENT_SECRET", "test-secret")


def _make_directive(
    namespace: str,
    name: str,
    *,
    token: str = "test-token",
    endpoint_id: str | None = None,
) -> dict:
    directive: dict = {
        "header": {
            "namespace": namespace,
            "name": name,
            "payloadVersion": "3",
            "messageId": "msg-1",
            "correlationToken": "corr-1",
        },
        "payload": {},
    }
    if endpoint_id:
        directive["endpoint"] = {
            "endpointId": endpoint_id,
            "scope": {"type": "BearerToken", "token": token},
        }
    else:
        directive["payload"]["scope"] = {"type": "BearerToken", "token": token}
    return directive


class TestLambdaHandler:
    def test_dispatches_discovery(self) -> None:
        event = {"directive": _make_directive("Alexa.Discovery", "Discover")}
        with patch("functions.skill.handler.handle_discovery", return_value={"ok": True}) as mock:
            result = lambda_handler(event, None)
        mock.assert_called_once()
        assert result == {"ok": True}

    def test_dispatches_power_control(self) -> None:
        event = {
            "directive": _make_directive("Alexa.PowerController", "TurnOn", endpoint_id="VIN1")
        }
        with patch(
            "functions.skill.handler.handle_power_control", return_value={"ok": True}
        ) as mock:
            result = lambda_handler(event, None)
        mock.assert_called_once()
        assert result == {"ok": True}

    def test_dispatches_report_state(self) -> None:
        event = {"directive": _make_directive("Alexa", "ReportState", endpoint_id="VIN1")}
        with patch(
            "functions.skill.handler.handle_report_state", return_value={"ok": True}
        ) as mock:
            lambda_handler(event, None)
        mock.assert_called_once()

    def test_unknown_directive_returns_error(self) -> None:
        event = {"directive": _make_directive("Unknown", "Unknown")}
        result = lambda_handler(event, None)
        assert result["event"]["header"]["name"] == "ErrorResponse"


class TestHandleDiscovery:
    @patch("functions.skill.handler.TeslaFleetClient")
    @patch("functions.skill.handler.VehicleService")
    def test_returns_endpoints(self, mock_svc_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        from halstela.models.vehicle import Vehicle

        mock_svc = mock_svc_cls.return_value
        mock_svc.get_vehicles.return_value = [
            Vehicle(id="1", vin="VIN1", display_name="My Tesla", state="online"),
        ]

        directive = _make_directive("Alexa.Discovery", "Discover")
        result = handle_discovery(directive)

        endpoints = result["event"]["payload"]["endpoints"]
        assert len(endpoints) == 1
        assert endpoints[0]["endpointId"] == "VIN1"
        assert endpoints[0]["friendlyName"] == "My Tesla"
        assert any(
            c["interface"] == "Alexa.TemperatureSensor" for c in endpoints[0]["capabilities"]
        )


class TestHandlePowerControl:
    @patch("functions.skill.handler.TeslaFleetClient")
    @patch("functions.skill.handler.VehicleService")
    def test_turn_on_success(self, mock_svc_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        from halstela.models.command_result import CommandResult

        mock_svc = mock_svc_cls.return_value
        mock_svc.start_air_conditioning.return_value = CommandResult(success=True, reason="")

        directive = _make_directive("Alexa.PowerController", "TurnOn", endpoint_id="VIN1")
        result = handle_power_control(directive)

        assert result["event"]["header"]["name"] == "Response"
        assert result["event"]["endpoint"]["endpointId"] == "VIN1"

    @patch("functions.skill.handler.TeslaFleetClient")
    @patch("functions.skill.handler.VehicleService")
    def test_turn_on_failure(self, mock_svc_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        from halstela.models.command_result import CommandResult

        mock_svc = mock_svc_cls.return_value
        mock_svc.start_air_conditioning.return_value = CommandResult(
            success=False, reason="vehicle_unavailable"
        )

        directive = _make_directive("Alexa.PowerController", "TurnOn", endpoint_id="VIN1")
        result = handle_power_control(directive)

        assert result["event"]["header"]["name"] == "ErrorResponse"


class TestHandleReportState:
    @patch("functions.skill.handler.TeslaFleetClient")
    @patch("functions.skill.handler.VehicleService")
    def test_reports_temperature(self, mock_svc_cls: MagicMock, mock_client_cls: MagicMock) -> None:
        from halstela.models.climate_state import ClimateState

        mock_svc = mock_svc_cls.return_value
        mock_svc.get_climate_state.return_value = ClimateState(
            inside_temp=24.5,
            outside_temp=15.0,
            is_climate_on=False,
            driver_temp_setting=22.0,
        )

        directive = _make_directive("Alexa", "ReportState", endpoint_id="VIN1")
        result = handle_report_state(directive)

        assert result["event"]["header"]["name"] == "StateReport"
        temp_props = [
            p
            for p in result["context"]["properties"]
            if p["namespace"] == "Alexa.TemperatureSensor"
        ]
        assert len(temp_props) == 1
        assert temp_props[0]["value"]["value"] == 24.5
        assert temp_props[0]["value"]["scale"] == "CELSIUS"


class TestErrorResponse:
    def test_builds_error(self) -> None:
        directive = _make_directive("Alexa", "Test", endpoint_id="VIN1")
        result = _error_response(directive, "INTERNAL_ERROR", "something broke")

        assert result["event"]["header"]["name"] == "ErrorResponse"
        assert result["event"]["payload"]["type"] == "INTERNAL_ERROR"
        assert result["event"]["payload"]["message"] == "something broke"
