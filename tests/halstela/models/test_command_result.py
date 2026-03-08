"""halstela.models.command_result のテスト"""

from halstela.models.command_result import CommandResult


class TestCommandResult:
    def test_success(self) -> None:
        r = CommandResult(success=True, reason="ok")
        assert r.success is True
        assert r.reason == "ok"

    def test_failure(self) -> None:
        r = CommandResult(success=False, reason="vehicle offline")
        assert r.success is False
