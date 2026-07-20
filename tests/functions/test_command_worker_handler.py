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
        mock_svc.start_air_conditioning.return_value = CommandResult(success=True, reason="")
        mock_create_client.return_value.__enter__.return_value = MagicMock()

        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        result = lambda_handler(event, None)

        assert result == {"success": True, "reason": ""}
        mock_svc.start_air_conditioning.assert_called_once_with("VIN1")
        mock_config_cls.from_env.assert_called_once()

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
        mock_svc.start_air_conditioning.return_value = CommandResult(
            success=False, reason="vehicle_unavailable"
        )
        mock_create_client.return_value.__enter__.return_value = MagicMock()

        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "auto_conditioning_start",
        }
        with pytest.raises(RuntimeError, match="Worker command failed"):
            lambda_handler(event, None)

    def test_unknown_command_raises(self) -> None:
        event = {
            "access_token": "token",
            "vehicle_id": "VIN1",
            "command": "honk_horn",
        }
        with pytest.raises(ValueError, match="Unsupported worker command"):
            lambda_handler(event, None)

    def test_invalid_payload_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required fields"):
            lambda_handler({"access_token": "token"}, None)
