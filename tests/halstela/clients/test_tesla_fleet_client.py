"""halstela.clients.tesla_fleet_client のテスト"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from halstela.clients.tesla_fleet_client import TeslaAPIError, TeslaFleetClient


@pytest.fixture
def mock_response() -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def client() -> TeslaFleetClient:
    with patch.object(httpx, "Client"):
        c = TeslaFleetClient("test-token", "https://example.com")
    return c


class TestGetVehicles:
    def test_returns_vehicle_list(self, client: TeslaFleetClient) -> None:
        vehicles = [{"id": 1, "vin": "VIN1", "display_name": "T1", "state": "online"}]
        client._client.get.return_value = MagicMock(
            json=lambda: {"response": vehicles},
            raise_for_status=MagicMock(),
        )

        result = client.get_vehicles()
        assert result == vehicles
        client._client.get.assert_called_once_with("/api/1/vehicles", params=None)

    def test_raises_on_bad_response(self, client: TeslaFleetClient) -> None:
        client._client.get.return_value = MagicMock(
            json=lambda: {"response": "not a list"},
            raise_for_status=MagicMock(),
        )

        with pytest.raises(TeslaAPIError):
            client.get_vehicles()


class TestGetVehicleData:
    def test_with_endpoints(self, client: TeslaFleetClient) -> None:
        data = {"climate_state": {"inside_temp": 22.0}}
        client._client.get.return_value = MagicMock(
            json=lambda: {"response": data},
            raise_for_status=MagicMock(),
        )

        result = client.get_vehicle_data("VIN1", endpoints=["climate_state"])
        assert result == data
        client._client.get.assert_called_once_with(
            "/api/1/vehicles/VIN1/vehicle_data",
            params={"endpoints": "climate_state"},
        )

    def test_without_endpoints(self, client: TeslaFleetClient) -> None:
        client._client.get.return_value = MagicMock(
            json=lambda: {"response": {}},
            raise_for_status=MagicMock(),
        )

        client.get_vehicle_data("VIN1")
        client._client.get.assert_called_once_with(
            "/api/1/vehicles/VIN1/vehicle_data",
            params={},
        )


class TestSendCommand:
    def test_sends_command(self, client: TeslaFleetClient) -> None:
        client._client.post.return_value = MagicMock(
            json=lambda: {"response": {"result": True, "reason": ""}},
            raise_for_status=MagicMock(),
        )

        result = client.send_command("VIN1", "auto_conditioning_start")
        assert result == {"result": True, "reason": ""}


class TestWakeUp:
    def test_wakes_up(self, client: TeslaFleetClient) -> None:
        client._client.post.return_value = MagicMock(
            json=lambda: {"response": {"state": "online"}},
            raise_for_status=MagicMock(),
        )

        result = client.wake_up("VIN1")
        assert result == {"state": "online"}


class TestHTTPError:
    def test_raises_tesla_api_error(self, client: TeslaFleetClient) -> None:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        client._client.get.return_value = MagicMock(
            raise_for_status=MagicMock(
                side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_resp)
            )
        )

        with pytest.raises(TeslaAPIError) as exc_info:
            client.get_vehicles()
        assert exc_info.value.status_code == 401
