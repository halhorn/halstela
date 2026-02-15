"""トークン管理モジュール"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TokenManager:
    """トークンの保存・読み込みを管理"""

    def __init__(self, token_file: Path):
        self.token_file = token_file

    def save(self, payload: dict[str, Any]) -> Path:
        """トークンを保存"""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        payload["obtained_at"] = int(time.time())
        self.token_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            self.token_file.chmod(0o600)
        except OSError:
            # 一部環境では chmod に失敗することがあるため続行する
            pass
        return self.token_file

    def load(self) -> dict[str, Any]:
        """トークンを読み込み"""
        if not self.token_file.exists():
            raise FileNotFoundError(f"トークンファイルが見つかりません: {self.token_file}")
        return json.loads(self.token_file.read_text(encoding="utf-8"))

    def get_access_token(self) -> str:
        """access_tokenを取得"""
        data = self.load()
        token = data.get("access_token")
        if not token:
            raise ValueError(f"{self.token_file} に access_token がありません。")
        return token

    def get_refresh_token(self) -> str:
        """refresh_tokenを取得"""
        data = self.load()
        token = data.get("refresh_token")
        if not token:
            raise ValueError(f"{self.token_file} に refresh_token がありません。")
        return token
