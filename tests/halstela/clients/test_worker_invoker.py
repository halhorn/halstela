"""halstela.clients.worker_invoker のテスト"""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from halstela.clients.worker_invoker import WorkerInvokeError, WorkerInvoker
from halstela.models.worker_command import WorkerCommand


class TestWorkerInvoker:
    def test_invoke_async_sends_event_payload(self) -> None:
        lambda_client = MagicMock()
        lambda_client.invoke.return_value = {"StatusCode": 202}
        invoker = WorkerInvoker("arn:aws:lambda:us-west-2:123:function:worker", lambda_client)
        command = WorkerCommand(
            access_token="token",
            vehicle_id="VIN1",
            command="auto_conditioning_start",
            correlation_token="corr-1",
        )

        invoker.invoke_async(command)

        kwargs: dict[str, Any] = lambda_client.invoke.call_args.kwargs
        assert kwargs["FunctionName"] == "arn:aws:lambda:us-west-2:123:function:worker"
        assert kwargs["InvocationType"] == "Event"
        assert json.loads(kwargs["Payload"].decode("utf-8")) == command.to_payload()

    def test_unexpected_status_code_raises(self) -> None:
        lambda_client = MagicMock()
        lambda_client.invoke.return_value = {"StatusCode": 400}
        invoker = WorkerInvoker("arn:worker", lambda_client)
        command = WorkerCommand(
            access_token="token",
            vehicle_id="VIN1",
            command="auto_conditioning_start",
        )

        with pytest.raises(WorkerInvokeError, match="Unexpected StatusCode"):
            invoker.invoke_async(command)

    def test_client_exception_is_wrapped(self) -> None:
        lambda_client = MagicMock()
        lambda_client.invoke.side_effect = RuntimeError("boom")
        invoker = WorkerInvoker("arn:worker", lambda_client)
        command = WorkerCommand(
            access_token="token",
            vehicle_id="VIN1",
            command="auto_conditioning_start",
        )

        with pytest.raises(WorkerInvokeError, match="Failed to invoke worker"):
            invoker.invoke_async(command)
