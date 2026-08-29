"""functions/command_worker/handler.py のテスト"""

from unittest.mock import MagicMock, patch

import pytest

from functions.command_worker.handler import lambda_handler
from halstela.models.command_result import CommandResult


class TestCommandWorkerHandler:
    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_success(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_start.return_value = CommandResult(success=True, reason="")
        mock_create_client.return_value.__enter__.return_value = MagicMock()

        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with patch("functions.command_worker.handler._send_change_report"):
            result = lambda_handler(event, None)

        assert result == {"success": True, "reason": ""}
        mock_svc.auto_conditioning_start.assert_called_once_with("VIN1")
        mock_config_cls.from_env.assert_called_once()

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_stop_success(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_stop.return_value = CommandResult(success=True, reason="")
        mock_create_client.return_value.__enter__.return_value = MagicMock()

        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_stop",
        }
        with patch("functions.command_worker.handler._send_change_report"):
            result = lambda_handler(event, None)

        assert result == {"success": True, "reason": ""}
        mock_svc.auto_conditioning_stop.assert_called_once_with("VIN1")
        mock_svc.auto_conditioning_start.assert_not_called()

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_api_failure_raises(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_start.return_value = CommandResult(
            success=False, reason="vehicle_unavailable"
        )
        mock_create_client.return_value.__enter__.return_value = MagicMock()

        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with (
            patch("functions.command_worker.handler._send_change_report"),
            pytest.raises(RuntimeError, match="Worker command failed"),
        ):
            lambda_handler(event, None)

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_unknown_command_raises(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_create_client.return_value.__enter__.return_value = MagicMock()
        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "honk_horn",
        }
        with pytest.raises(ValueError, match="Unsupported worker command"):
            lambda_handler(event, None)
        mock_svc_cls.return_value.auto_conditioning_start.assert_not_called()
        assert "Invalid worker command" in caplog.text

    def test_invalid_payload_raises(self, caplog: pytest.LogCaptureFixture) -> None:
        with pytest.raises(ValueError, match="missing required fields"):
            lambda_handler({"access_token": "token"}, None)
        assert "Invalid worker command" in caplog.text

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_success_sends_change_report(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        from halstela.models.climate_state import ClimateState

        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_start.return_value = CommandResult(success=True, reason="")
        mock_svc.get_climate_state.return_value = ClimateState(
            inside_temp=22.0, outside_temp=10.0, is_climate_on=True, driver_temp_setting=22.0
        )
        mock_create_client.return_value.__enter__.return_value = MagicMock()
        mock_gateway = MagicMock()
        mock_gateway.__enter__.return_value = mock_gateway
        mock_gateway.__exit__.return_value = False
        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with patch(
            "functions.command_worker.handler._create_event_gateway_client",
            return_value=mock_gateway,
        ):
            lambda_handler(event, None)

        mock_gateway.send_change_report.assert_called_once()
        kwargs = mock_gateway.send_change_report.call_args.kwargs
        assert kwargs["endpoint_id"] == "VIN1"
        assert kwargs["changed"][0].name == "powerState"
        assert kwargs["changed"][0].value == "ON"
        assert [p.name for p in kwargs["context"]] == ["temperature", "connectivity"]

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_command_failure_sends_observed_power_off(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        from halstela.models.climate_state import ClimateState

        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_start.return_value = CommandResult(
            success=False, reason="vehicle_unavailable"
        )
        mock_svc.get_climate_state.return_value = ClimateState(
            inside_temp=18.0, outside_temp=10.0, is_climate_on=False, driver_temp_setting=22.0
        )
        mock_create_client.return_value.__enter__.return_value = MagicMock()
        mock_gateway = MagicMock()
        mock_gateway.__enter__.return_value = mock_gateway
        mock_gateway.__exit__.return_value = False
        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with (
            patch(
                "functions.command_worker.handler._create_event_gateway_client",
                return_value=mock_gateway,
            ),
            pytest.raises(RuntimeError, match="Worker command failed"),
        ):
            lambda_handler(event, None)

        kwargs = mock_gateway.send_change_report.call_args.kwargs
        assert kwargs["changed"][0].name == "powerState"
        assert kwargs["changed"][0].value == "OFF"

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_change_report_failure_does_not_fail_worker(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        from halstela.alexa.event_gateway import EventGatewayError

        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_start.return_value = CommandResult(success=True, reason="")
        mock_create_client.return_value.__enter__.return_value = MagicMock()
        mock_gateway = MagicMock()
        mock_gateway.__enter__.return_value = mock_gateway
        mock_gateway.__exit__.return_value = False
        mock_gateway.send_change_report.side_effect = EventGatewayError(500, "down")
        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with patch(
            "functions.command_worker.handler._create_event_gateway_client",
            return_value=mock_gateway,
        ):
            result = lambda_handler(event, None)
        assert result == {"success": True, "reason": ""}

    @patch("functions.command_worker.handler.create_fleet_client")
    @patch("functions.command_worker.handler.VehicleService")
    @patch("functions.command_worker.handler.TeslaConfig")
    def test_climate_fetch_failure_skips_change_report(
        self,
        mock_config_cls: MagicMock,
        mock_svc_cls: MagicMock,
        mock_create_client: MagicMock,
    ) -> None:
        mock_svc = mock_svc_cls.return_value
        mock_svc.auto_conditioning_start.return_value = CommandResult(success=True, reason="")
        mock_svc.get_climate_state.side_effect = RuntimeError("vehicle asleep")
        mock_create_client.return_value.__enter__.return_value = MagicMock()
        mock_gateway = MagicMock()
        mock_gateway.__enter__.return_value = mock_gateway
        mock_gateway.__exit__.return_value = False
        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with patch(
            "functions.command_worker.handler._create_event_gateway_client",
            return_value=mock_gateway,
        ):
            result = lambda_handler(event, None)

        assert result == {"success": True, "reason": ""}
        mock_gateway.send_change_report.assert_not_called()
