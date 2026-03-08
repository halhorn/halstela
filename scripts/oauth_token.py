#!/usr/bin/env -S uv run python
"""Tesla OAuth2 トークン取得/更新スクリプト。"""

import argparse
import json
import sys

from halstela.auth.oauth import TeslaOAuth2
from halstela.auth.oauth_callback_server import OAuthCallbackServer
from halstela.auth.token import TokenManager
from halstela.config import TeslaConfig

CALLBACK_TIMEOUT = 300.0


def main() -> int:
    args = _parse_args()

    try:
        config = TeslaConfig.from_env()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        oauth = TeslaOAuth2(config)
        if args.refresh:
            return _run_refresh(oauth, config)
        return _run_authorization_flow(oauth, config, open_browser=not args.no_open_browser)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


def _run_refresh(oauth: TeslaOAuth2, config: TeslaConfig) -> int:
    payload = oauth.refresh_token()
    token_manager = TokenManager(config.get_token_file_path())
    path = token_manager.save(payload)
    _print_token_result(str(path), payload, message="token を更新しました")
    return 0


def _run_authorization_flow(
    oauth: TeslaOAuth2,
    config: TeslaConfig,
    open_browser: bool,
) -> int:
    callback_server = OAuthCallbackServer()
    url, _ = oauth.create_authorization_url(
        redirect_uri=callback_server.redirect_uri,
        scopes=config.oauth_scopes,
    )
    _open_auth_url(url, open_browser)

    print("\nローカルサーバーでコールバックを待機しています...")
    result = callback_server.wait_for_code(timeout=CALLBACK_TIMEOUT)

    if result.error:
        msg = (
            "タイムアウトまたは code が取得できませんでした。"
            if result.error == "timeout"
            else result.error
        )
        print(f"[ERROR] {msg}", file=sys.stderr)
        return 1
    if not result.code:
        print("[ERROR] code が取得できませんでした。", file=sys.stderr)
        return 1

    payload = oauth.fetch_token(code=result.code, redirect_uri=callback_server.redirect_uri)
    token_manager = TokenManager(config.get_token_file_path())
    path = token_manager.save(payload)
    print()
    _print_token_result(str(path), payload)
    return 0


def _open_auth_url(url: str, open_browser: bool) -> None:
    print("以下の URL をブラウザで開いて認証してください:")
    print(url)
    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
            print("ブラウザを開きました。認証後、このウィンドウに戻ってください。")
        except Exception:  # noqa: BLE001
            print("ブラウザの起動に失敗しました。上記 URL を手動で開いてください。")
    else:
        print("認証後、リダイレクト先で code が自動で取得されます。")


def _print_token_result(path: str, payload: dict, message: str = "token を保存しました") -> None:
    print(f"{message}: {path}")
    print(
        json.dumps(
            {k: payload.get(k) for k in ("token_type", "expires_in", "scope")},
            ensure_ascii=False,
        )
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tesla OAuth2 token utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="refresh token で更新",
    )
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="ブラウザを自動で開かない",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
