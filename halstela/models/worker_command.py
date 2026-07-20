"""Worker Lambda へ渡すコマンドペイロード"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkerCommand:
    """Skill → Worker のペイロード契約。

    access_token を含むため、ペイロード全体をログ出力しないこと。
    """

    access_token: str
    vehicle_id: str
    command: str
    correlation_token: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "access_token": self.access_token,
            "vehicle_id": self.vehicle_id,
            "command": self.command,
        }
        if self.correlation_token is not None:
            payload["correlation_token"] = self.correlation_token
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkerCommand":
        missing = [key for key in ("access_token", "vehicle_id", "command") if key not in payload]
        if missing:
            raise ValueError(f"WorkerCommand payload missing required fields: {missing}")
        correlation = payload.get("correlation_token")
        return cls(
            access_token=str(payload["access_token"]),
            vehicle_id=str(payload["vehicle_id"]),
            command=str(payload["command"]),
            correlation_token=str(correlation) if correlation is not None else None,
        )
