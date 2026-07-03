"""設定管理モジュール"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

_ssm_cache: dict[str, dict[str, str]] = {}


def _read_ssm(prefix: str) -> dict[str, str]:
    """SSM Parameter Store からプレフィックス配下のパラメータを一括取得（結果はキャッシュ）。"""
    if prefix in _ssm_cache:
        return _ssm_cache[prefix]

    import boto3

    ssm = boto3.client("ssm")
    names = [
        f"{prefix}/tesla-client-id",
        f"{prefix}/tesla-client-secret",
        f"{prefix}/tesla-private-key",
    ]
    resp = ssm.get_parameters(Names=names, WithDecryption=True)

    result = {p["Name"].rsplit("/", 1)[-1]: p["Value"] for p in resp["Parameters"]}
    _ssm_cache[prefix] = result
    return result


def _load_private_key_from_file() -> str | None:
    """ローカル環境で秘密鍵ファイルを読み込む。"""
    key_file = os.environ.get("TESLA_PRIVATE_KEY_FILE")
    if key_file:
        path = Path(key_file)
    else:
        repo_root = Path(__file__).resolve().parents[1]
        path = repo_root / "secret" / "private.pem"

    if path.exists():
        return path.read_text()
    return None


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
    private_key_pem: str | None = None

    @classmethod
    def from_env(cls) -> "TeslaConfig":
        """環境変数または SSM Parameter Store から設定を読み込む。

        Lambda 環境では SSM_PREFIX が設定されており、SSM から秘密情報を取得する。
        ローカル開発では .env から読み込む。
        """
        load_dotenv()

        ssm_prefix = os.environ.get("SSM_PREFIX")
        if ssm_prefix:
            params = _read_ssm(ssm_prefix)
            client_id = params.get("tesla-client-id", "")
            client_secret = params.get("tesla-client-secret", "")
            private_key_pem = params.get("tesla-private-key")
        else:
            client_id = os.environ.get("TESLA_CLIENT_ID", "")
            client_secret = os.environ.get("TESLA_CLIENT_SECRET", "")
            private_key_pem = _load_private_key_from_file()

        if not client_id:
            raise ValueError("TESLA_CLIENT_ID is required (set in .env or SSM)")
        if not client_secret:
            raise ValueError("TESLA_CLIENT_SECRET is required (set in .env or SSM)")

        kwargs: dict[str, Any] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "private_key_pem": private_key_pem,
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
