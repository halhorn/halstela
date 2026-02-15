"""設定管理モジュール"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class TeslaConfig(BaseSettings):
    """Tesla API設定"""

    model_config = SettingsConfigDict(
        env_prefix="TESLA_",
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # 必須環境変数
    client_id: str
    client_secret: str

    # オプション環境変数
    auth_url: str = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/authorize"
    token_url: str = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
    api_base_url: str = "https://fleet-api.prd.na.vn.cloud.tesla.com"
    oauth_scopes: str = "openid offline_access vehicle_device_data"
    partner_scope: str = "openid offline_access"
    token_file: Optional[str] = None

    def get_token_file_path(self) -> Path:
        """トークンファイルのパスを取得"""
        if self.token_file:
            return Path(self.token_file)
        repo_root = Path(__file__).resolve().parents[2]
        return repo_root / "secret" / "token.json"
