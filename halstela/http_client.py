"""HTTPクライアントモジュール"""

from __future__ import annotations

import json
from typing import Any

import httpx


class TeslaHTTPClient:
    """Tesla API用HTTPクライアント"""

    def __init__(self, base_url: str, timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """クライアントを閉じる"""
        self._client.close()

    def post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        """application/x-www-form-urlencoded形式でPOSTリクエスト"""
        try:
            response = self._client.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            body_text = exc.response.text
            raise RuntimeError(f"HTTP {exc.response.status_code} {url}\n{body_text}") from exc

    def get_json(self, path: str, token: str) -> dict[str, Any]:
        """Bearerトークン付きGETリクエスト"""
        url = f"{self.base_url}{path}"
        try:
            response = self._client.get(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            body_text = exc.response.text
            raise RuntimeError(f"HTTP {exc.response.status_code} {url}\n{body_text}") from exc

    def post_json(self, path: str, token: str, data: dict[str, Any]) -> dict[str, Any]:
        """Bearerトークン付きPOSTリクエスト"""
        url = f"{self.base_url}{path}"
        try:
            response = self._client.post(
                url,
                json=data,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            body_text = exc.response.text
            raise RuntimeError(f"HTTP {exc.response.status_code} {url}\n{body_text}") from exc
