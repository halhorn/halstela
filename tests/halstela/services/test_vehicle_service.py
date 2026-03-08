"""halstela.services.vehicle_service のテスト"""

from unittest.mock import MagicMock

import pytest

from halstela.clients.tesla_fleet_client import TeslaAPIError
from halstela.models.climate_state import ClimateState
from halstela.models.command_result import CommandResult
from halstela.models.vehicle import Vehicle
from halstela.services.vehicle_service import VehicleService


class TestGetVehicles:
    def test_converts_raw_to_vehicles(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicles.return_value = [
            {"id": 1, "id_s": "100", "vin": "VIN1", "display_name": "My Tesla", "state": "online"},
        ]

        result = vehicle_service.get_vehicles()

        assert len(result) == 1
        assert result[0] == Vehicle(id="100", vin="VIN1", display_name="My Tesla", state="online")

    def test_handles_missing_fields(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicles.return_value = [{"id": 1}]

        result = vehicle_service.get_vehicles()
        assert result[0].vin == ""
        assert result[0].display_name == ""


class TestGetVehicleData:
    def test_ensures_awake_then_returns_data(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicle.return_value = {"state": "online"}
        mock_client.get_vehicle_data.return_value = {
            "climate_state": {"inside_temp": 20.0},
            "charge_state": {"battery_level": 80},
        }

        result = vehicle_service.get_vehicle_data("VIN1")

        mock_client.get_vehicle.assert_called_once_with("VIN1")
        mock_client.get_vehicle_data.assert_called_once_with("VIN1", endpoints=None)
        assert result["charge_state"]["battery_level"] == 80

    def test_wakes_up_sleeping_vehicle_before_fetching(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicle.side_effect = [
            TeslaAPIError(408, "Request Timeout"),
            {"state": "online"},
        ]
        mock_client.get_vehicle_data.return_value = {"climate_state": {"inside_temp": 22.0}}

        result = vehicle_service.get_vehicle_data("VIN1")

        mock_client.wake_up.assert_called_once_with("VIN1")
        assert result["climate_state"]["inside_temp"] == 22.0

    def test_passes_endpoints(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicle.return_value = {"state": "online"}
        mock_client.get_vehicle_data.return_value = {"climate_state": {"inside_temp": 20.0}}

        vehicle_service.get_vehicle_data("VIN1", endpoints=["climate_state"])

        mock_client.get_vehicle_data.assert_called_once_with("VIN1", endpoints=["climate_state"])


class TestGetClimateState:
    def test_returns_climate_state(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicle.return_value = {"state": "online"}
        mock_client.get_vehicle_data.return_value = {
            "climate_state": {
                "inside_temp": 25.0,
                "outside_temp": 18.0,
                "is_climate_on": True,
                "driver_temp_setting": 22.0,
            }
        }

        result = vehicle_service.get_climate_state("VIN1")

        assert result == ClimateState(
            inside_temp=25.0,
            outside_temp=18.0,
            is_climate_on=True,
            driver_temp_setting=22.0,
        )
        mock_client.get_vehicle_data.assert_called_once_with("VIN1", endpoints=["climate_state"])


class TestStartAirConditioning:
    def test_success(self, vehicle_service: VehicleService, mock_client: MagicMock) -> None:
        mock_client.get_vehicle.return_value = {"state": "online"}
        mock_client.send_command.return_value = {"result": True, "reason": ""}

        result = vehicle_service.start_air_conditioning("VIN1")

        assert result == CommandResult(success=True, reason="")
        mock_client.send_command.assert_called_once_with("VIN1", "auto_conditioning_start")


class TestEnsureAwake:
    def test_already_online(self, vehicle_service: VehicleService, mock_client: MagicMock) -> None:
        mock_client.get_vehicle.return_value = {"state": "online"}

        vehicle_service.ensure_awake("VIN1")

        mock_client.wake_up.assert_not_called()

    def test_wakes_up_asleep_vehicle(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicle.side_effect = [
            {"state": "asleep"},
            {"state": "online"},
        ]

        vehicle_service.ensure_awake("VIN1", timeout=10.0)

        mock_client.wake_up.assert_called_once_with("VIN1")

    def test_handles_408_as_asleep(
        self, vehicle_service: VehicleService, mock_client: MagicMock
    ) -> None:
        mock_client.get_vehicle.side_effect = [
            TeslaAPIError(408, "Request Timeout"),
            {"state": "online"},
        ]

        vehicle_service.ensure_awake("VIN1", timeout=10.0)

        mock_client.wake_up.assert_called_once()

    def test_timeout_raises(self, vehicle_service: VehicleService, mock_client: MagicMock) -> None:
        mock_client.get_vehicle.return_value = {"state": "asleep"}

        with pytest.raises(TimeoutError):
            vehicle_service.ensure_awake("VIN1", timeout=0.1)
