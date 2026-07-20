"""Worker Lambda への非同期 invoke クライアント"""

from __future__ import annotations

import json
from typing import Any

from halstela.models.worker_command import WorkerCommand


class WorkerInvokeError(Exception):
    """Worker Lambda を起動できなかったことを表す。"""


class WorkerInvoker:
    """Worker Lambda への非同期 invoke（InvocationType=Event）。

    boto3 をこのクラスの外に漏らさない。テストでは lambda_client を注入する。
    """

    def __init__(self, function_arn: str, lambda_client: Any | None = None) -> None:
        self._function_arn = function_arn
        if lambda_client is None:
            import boto3

            lambda_client = boto3.client("lambda")
        self._lambda_client = lambda_client

    def invoke_async(self, command: WorkerCommand) -> None:
        try:
            response = self._lambda_client.invoke(
                FunctionName=self._function_arn,
                InvocationType="Event",
                Payload=json.dumps(command.to_payload()).encode("utf-8"),
            )
        except Exception as exc:
            raise WorkerInvokeError(f"Failed to invoke worker: {exc}") from exc

        status_code = int(response.get("StatusCode", 0))
        if status_code != 202:
            raise WorkerInvokeError(
                f"Unexpected StatusCode from worker invoke: {status_code}"
            )
