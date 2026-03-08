"""コマンド実行結果データクラス"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    success: bool
    reason: str
