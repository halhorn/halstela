"""共通テストフィクスチャ"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from halstela.clients.tesla_fleet_client import TeslaFleetClient
from halstela.services.vehicle_service import VehicleService


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock(spec=TeslaFleetClient)


@pytest.fixture
def vehicle_service(mock_client: MagicMock) -> VehicleService:
    return VehicleService(mock_client)
