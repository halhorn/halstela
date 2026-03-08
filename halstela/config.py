"""設定管理モジュール"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class TeslaConfig:
    client_id: str
    client_secret: str
    fleet_api_base_url: str = "https://fleet-api.prd.na.vn.cloud.tesla.com"
    auth_url: str = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/authorize"
    token_url: str = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
    oauth_scopes: str = "openid offline_access vehicle_device_data vehicle_cmds vehicle_location"
    partner_scope: str = "openid offline_access"
    token_file: str | None = None

    @classmethod
    def from_env(cls) -> "TeslaConfig":
        """環境変数から設定を読み込む。.env ファイルがあれば先に読み込む。"""
        load_dotenv()
        client_id = os.environ.get("TESLA_CLIENT_ID")
        if not client_id:
            raise ValueError("TESLA_CLIENT_ID environment variable is required")
        client_secret = os.environ.get("TESLA_CLIENT_SECRET")
        if not client_secret:
            raise ValueError("TESLA_CLIENT_SECRET environment variable is required")

        kwargs: dict[str, str] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
        optional_fields = (
            "fleet_api_base_url",
            "auth_url",
            "token_url",
            "oauth_scopes",
            "partner_scope",
            "token_file",
        )
        for field in optional_fields:
            value = os.environ.get(f"TESLA_{field.upper()}")
            if value is not None:
                kwargs[field] = value

        return cls(**kwargs)

    def get_token_file_path(self) -> Path:
        if self.token_file:
            return Path(self.token_file)
        repo_root = Path(__file__).resolve().parents[1]
        return repo_root / "secret" / "token.json"
