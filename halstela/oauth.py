"""OAuth2管理モジュール（authlib使用）"""

from __future__ import annotations

import secrets
from typing import Any

from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuth2Client

from halstela.config import TeslaConfig
from halstela.http_client import TeslaHTTPClient
from halstela.token import TokenManager


class TeslaOAuth2:
    """Tesla OAuth2クライアント"""

    def __init__(self, config: TeslaConfig):
        self.config = config
        self.client = OAuth2Client(
            client_id=config.client_id,
            client_secret=config.client_secret,
            token_endpoint=config.token_url,
        )

    def create_authorization_url(
        self,
        redirect_uri: str,
        scopes: str | None = None,
        state: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
    ) -> tuple[str, str]:
        """認可URLを生成"""
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
        """authorization codeをトークンに交換"""
        # authlibのfetch_tokenがclient_idを正しく送信しない場合があるため、
        # 直接HTTPリクエストを送信する
        body = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            body["code_verifier"] = code_verifier

        with TeslaHTTPClient(self.config.token_url) as http_client:
            return http_client.post_form(self.config.token_url, body)

    def refresh_token(self, refresh_token: str | None = None) -> dict[str, Any]:
        """refresh tokenでトークンを更新"""
        if refresh_token is None:
            token_manager = TokenManager(self.config.get_token_file_path())
            refresh_token = token_manager.get_refresh_token()

        token = self.client.refresh_token(
            self.config.token_url,
            refresh_token=refresh_token,
        )
        result = dict(token)

        # refresh tokenが省略される実装向けに現行値を保持
        if "refresh_token" not in result:
            result["refresh_token"] = refresh_token

        return result

    def get_partner_token(self) -> str:
        """client_credentialsでpartner tokenを取得"""
        with TeslaHTTPClient(self.config.token_url) as http_client:
            payload = http_client.post_form(
                self.config.token_url,
                {
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": self.config.partner_scope,
                },
            )
            token = payload.get("access_token")
            if not token:
                raise RuntimeError(f"partner token 取得に失敗しました: {payload}")
            return str(token)
