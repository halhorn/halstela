"""halstela.models.worker_command のテスト"""

import pytest

from halstela.models.worker_command import WorkerCommand


class TestWorkerCommand:
    def test_roundtrip_with_correlation_token(self) -> None:
        original = WorkerCommand(
            access_token="token",
            vehicle_id="VIN1",
            command="auto_conditioning_start",
            correlation_token="corr-1",
        )
        restored = WorkerCommand.from_payload(original.to_payload())
        assert restored == original

    def test_roundtrip_without_correlation_token(self) -> None:
        original = WorkerCommand(
            access_token="token",
            vehicle_id="VIN1",
            command="auto_conditioning_start",
        )
        payload = original.to_payload()
        assert "correlation_token" not in payload
        restored = WorkerCommand.from_payload(payload)
        assert restored.correlation_token is None
        assert restored.access_token == "token"
        assert restored.vehicle_id == "VIN1"
        assert restored.command == "auto_conditioning_start"

    def test_from_payload_missing_required_fields(self) -> None:
        with pytest.raises(ValueError, match="missing required fields"):
            WorkerCommand.from_payload({"access_token": "token"})
