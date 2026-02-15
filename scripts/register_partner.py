#!/usr/bin/env -S uv run python
"""
Tesla Fleet API の partner account 登録を行うスクリプト

やること:
1) client_credentials で partner token を取得
2) /api/1/partner_accounts に domain を登録
"""

from __future__ import annotations

import json
import sys

from halstela.config import TeslaConfig
from halstela.http_client import TeslaHTTPClient
from halstela.oauth import TeslaOAuth2

DOMAIN = "halhorn.github.io"


def main() -> int:
    """メイン関数"""
    # 設定読み込み
    try:
        config = TeslaConfig()
    except Exception as exc:
        print(f"[ERROR] 設定の読み込みに失敗しました: {exc}", file=sys.stderr)
        return 1

    try:
        oauth = TeslaOAuth2(config)
        token = oauth.get_partner_token()

        with TeslaHTTPClient(config.api_base_url) as http_client:
            payload = http_client.post_json(
                "/api/1/partner_accounts",
                token,
                {"domain": DOMAIN},
            )
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
