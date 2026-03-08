"""コマンド実行結果データクラス"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    success: bool
    reason: str
