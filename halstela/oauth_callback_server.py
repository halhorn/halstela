"""
OAuth2 認可コード受け取り用のローカルコールバックサーバー。

リダイレクト URI で返ってきた code を待ち受け、1 リクエスト受信後にサーバーを終了する。
"""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from urllib.parse import parse_qs, urlparse

# デフォルトのコールバック設定（OAuth 登録とサーバーで共通利用）
CALLBACK_HOST = "localhost"
CALLBACK_PORT = 3000
CALLBACK_PATH = "/callback"
REDIRECT_URI = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"


@dataclass
class OAuthCallbackResult:
    """コールバック受信結果"""

    code: str | None
    """認可コード。取得できた場合のみセット"""
    error: str | None
    """エラー時のみメッセージをセット（code なし・タイムアウトなど）"""


class OAuthCallbackServer:
    """
    OAuth2 認可コードをリダイレクトで受け取るためのローカルサーバー。

    リダイレクト URI に届いた code を待ち受け、1 リクエスト受信後に終了する。
    """

    def __init__(
        self,
        *,
        host: str = CALLBACK_HOST,
        port: int = CALLBACK_PORT,
        path: str = CALLBACK_PATH,
    ) -> None:
        self.host = host
        self.port = port
        self.path = path

    @property
    def redirect_uri(self) -> str:
        """OAuth の redirect_uri に登録する値"""
        return f"http://{self.host}:{self.port}{self.path}"

    def wait_for_code(self, timeout: float = 300.0) -> OAuthCallbackResult:
        """
        サーバーを起動し、コールバックで code が届くまで待つ。

        Args:
            timeout: 待機秒数。この時間内にリクエストがなければタイムアウト。

        Returns:
            受信結果。code があれば result.code、エラー時は result.error を参照。
        """
        result_holder: dict = {}
        done = Event()
        server = HTTPServer(
            (self.host, self.port),
            self._make_handler(result_holder, done),
        )
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        # ハンドラ内で shutdown() を呼ぶとデッドロックするため、メインスレッドで待機してから shutdown
        done.wait(timeout=timeout)
        server.shutdown()
        thread.join(timeout=2.0)

        if "error" in result_holder:
            return OAuthCallbackResult(code=None, error=result_holder["error"])
        if "code" in result_holder:
            return OAuthCallbackResult(code=result_holder["code"], error=None)
        return OAuthCallbackResult(code=None, error="timeout")

    def _make_handler(
        self,
        result_holder: dict,
        done: Event,
    ) -> type[BaseHTTPRequestHandler]:
        path = self.path

        class _CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(inner_self) -> None:
                parsed = urlparse(inner_self.path)
                if parsed.path != path:
                    inner_self.send_error(404, "Not Found")
                    done.set()
                    return

                query = parse_qs(parsed.query)
                code_list = query.get("code")
                if not code_list or not code_list[0]:
                    inner_self._send_html(
                        400, "認証に失敗しました", "code が取得できませんでした。"
                    )
                    result_holder["error"] = "code not found"
                    done.set()
                    return

                code = code_list[0].strip()
                result_holder["code"] = code

                inner_self._send_html(
                    200,
                    "認証が完了しました",
                    "トークンを保存しました。このウィンドウを閉じてください。",
                )
                done.set()

            def _send_html(inner_self, status: int, title: str, body: str) -> None:
                inner_self.send_response(status)
                inner_self.send_header("Content-type", "text/html; charset=utf-8")
                inner_self.end_headers()
                html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:sans-serif;max-width:480px;margin:2em auto;padding:1em;">
<h2>{title}</h2>
<p>{body}</p>
</body></html>"""
                inner_self.wfile.write(html.encode("utf-8"))

            def log_message(inner_self, format: str, *args: object) -> None:
                pass

        return _CallbackHandler
