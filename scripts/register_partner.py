#!/usr/bin/env -S uv run python
"""Tesla Fleet API の partner account 登録を行うスクリプト。"""

from __future__ import annotations

import json
import sys

import httpx

from halstela.auth.oauth import TeslaOAuth2
from halstela.config import TeslaConfig

DOMAIN = "halhorn.github.io"


def main() -> int:
    try:
        config = TeslaConfig.from_env()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        oauth = TeslaOAuth2(config)
        token = oauth.get_partner_token()

        with httpx.Client(timeout=20.0) as client:
            response = client.post(
                f"{config.fleet_api_base_url}/api/1/partner_accounts",
                json={"domain": DOMAIN},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
