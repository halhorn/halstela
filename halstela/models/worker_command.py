"""Worker Lambda へ渡すコマンドペイロード"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkerCommand:
    """Skill → Worker のペイロード契約。

    access_token を含むため、ペイロード全体をログ出力しないこと。
    コマンド固有の引数は params に載せる（例: params["driver_temp"]）。
    """

    access_token: str
    vehicle_id: str
    command: str
    correlation_token: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "access_token": self.access_token,
            "vehicle_id": self.vehicle_id,
            "command": self.command,
        }
        if self.correlation_token is not None:
            payload["correlation_token"] = self.correlation_token
        if self.params:
            payload["params"] = self.params
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WorkerCommand":
        missing = [key for key in ("access_token", "vehicle_id", "command") if key not in payload]
        if missing:
            raise ValueError(f"WorkerCommand payload missing required fields: {missing}")
        raw_params = payload.get("params", {})
        if not isinstance(raw_params, dict):
            raise ValueError("WorkerCommand params must be an object")
        correlation = payload.get("correlation_token")
        return cls(
            access_token=str(payload["access_token"]),
            vehicle_id=str(payload["vehicle_id"]),
            command=str(payload["command"]),
            correlation_token=str(correlation) if correlation is not None else None,
            params=raw_params,
        )
