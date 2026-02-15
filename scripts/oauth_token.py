#!/usr/bin/env -S uv run python
"""
Tesla OAuth2 トークン取得用の最小スクリプト（authlib使用版）。

実行すると認可URLを表示し、codeの入力を待ちます。
codeを入力すると、tokenに交換して保存します。
"""

from __future__ import annotations

import argparse
import json
import sys

from halstela.config import TeslaConfig
from halstela.oauth import TeslaOAuth2
from halstela.token import TokenManager

# 定数
REDIRECT_URI = "http://localhost:3000/callback"


def main() -> int:
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="Tesla OAuth2 token utility\n\n実行すると認可URLを表示し、codeの入力を待ちます。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="refresh tokenで更新（code入力は不要）",
    )
    args = parser.parse_args()

    # 設定読み込み
    try:
        config = TeslaConfig()
    except Exception as exc:
        print(f"[ERROR] 設定の読み込みに失敗しました: {exc}", file=sys.stderr)
        return 1

    try:
        oauth = TeslaOAuth2(config)

        if args.refresh:
            # refresh tokenで更新
            payload = oauth.refresh_token()
            token_manager = TokenManager(config.get_token_file_path())
            path = token_manager.save(payload)
            print(f"token を更新しました: {path}")
            print(
                json.dumps(
                    {k: payload.get(k) for k in ("token_type", "expires_in", "scope")},
                    ensure_ascii=False,
                )
            )
            return 0

        # 認可URLを生成して表示
        url, _ = oauth.create_authorization_url(
            redirect_uri=REDIRECT_URI,
            scopes=config.oauth_scopes,
        )
        print("以下のURLをブラウザで開いて認証してください:")
        print(url)
        print("\n認証後、localhostにリダイレクトされたURLからcodeパラメータを取り出してください。")
        print("\ncodeを入力してください: ", end="", flush=True)

        # code入力を待つ
        code = input().strip()
        if not code:
            print("[ERROR] codeが入力されませんでした。", file=sys.stderr)
            return 1

        # codeをtokenに交換
        payload = oauth.fetch_token(
            code=code,
            redirect_uri=REDIRECT_URI,
        )

        token_manager = TokenManager(config.get_token_file_path())
        path = token_manager.save(payload)
        print(f"\ntoken を保存しました: {path}")
        print(
            json.dumps(
                {k: payload.get(k) for k in ("token_type", "expires_in", "scope")},
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
