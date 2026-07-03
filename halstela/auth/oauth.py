"""OAuth2 管理モジュール（authlib 使用）"""

import secrets
from typing import Any

from authlib.integrations.httpx_client import OAuth2Client

from halstela.auth.token import TokenManager
from halstela.config import TeslaConfig


class TeslaOAuth2:
    """Tesla OAuth2 クライアント（CLI スクリプト用）

    Tesla の Token Endpoint は client_id / client_secret を
    リクエストボディで受け取るため ``client_secret_post`` を使う。
    """

    def __init__(self, config: TeslaConfig) -> None:
        self.config = config
        self.client = OAuth2Client(
            client_id=config.client_id,
            client_secret=config.client_secret,
            token_endpoint=config.token_url,
            token_endpoint_auth_method="client_secret_post",
            scope=config.oauth_scopes,
        )

    def create_authorization_url(
        self,
        redirect_uri: str,
        scopes: str | None = None,
        state: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
    ) -> tuple[str, str]:
        """認可 URL を生成"""
        if state is None:
            state = secrets.token_urlsafe(24)

        params: dict[str, Any] = {
            "redirect_uri": redirect_uri,
            "scope": scopes or self.config.oauth_scopes,
            "state": state,
        }

        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method

        url, _ = self.client.create_authorization_url(
            self.config.auth_url,
            **params,
        )
        return url, state

    def fetch_token(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict[str, Any]:
        """authorization code をトークンに交換"""
        params: dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "audience": self.config.fleet_api_base_url,
        }
        if code_verifier:
            params["code_verifier"] = code_verifier

        token = self.client.fetch_token(self.config.token_url, **params)
        return dict(token)

    def refresh_token(self, refresh_token: str | None = None) -> dict[str, Any]:
        """refresh token でトークンを更新"""
        if refresh_token is None:
            token_manager = TokenManager(self.config.get_token_file_path())
            refresh_token = token_manager.get_refresh_token()

        token = self.client.refresh_token(
            self.config.token_url,
            refresh_token=refresh_token,
            audience=self.config.fleet_api_base_url,
        )
        result = dict(token)

        if "refresh_token" not in result:
            result["refresh_token"] = refresh_token

        return result

    def get_partner_token(self) -> str:
        """client_credentials で partner token を取得"""
        token = self.client.fetch_token(
            self.config.token_url,
            grant_type="client_credentials",
            scope=self.config.partner_scope,
        )

        access_token = token.get("access_token")
        if not access_token:
            raise RuntimeError(f"partner token 取得に失敗しました: {dict(token)}")
        return str(access_token)
