#!/usr/bin/env python3
"""Account Linking を SMAPI で設定する。

TokenProxyUrl を CloudFormation Outputs から取得し、
Tesla OAuth の設定と合わせて Account Linking を構成する。

用法: ./scripts/setup_account_linking.py dev | prd
要:   .env に TESLA_CLIENT_ID / TESLA_CLIENT_SECRET を設定。
      sam deploy が完了していること（TokenProxyUrl が必要）。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASK_RESOURCES = REPO_ROOT / "ask-resources.json"
ENV_FILE = REPO_ROOT / ".env"

ENVS = {
    "dev": {"profile": "halhorn-dev", "aws_profile": "halhorn-dev"},
    "prd": {"profile": "halhorn-prd", "aws_profile": "halhorn-prd"},
}

STACK_NAME = "halstela"
REGION = "us-west-2"

TESLA_AUTH_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/authorize"
SCOPES = ["openid", "vehicle_device_data", "vehicle_cmds", "offline_access"]


def load_dotenv() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def run(cmd: list[str], *, check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout


def get_skill_id(profile: str) -> str:
    data = json.loads(ASK_RESOURCES.read_text())
    skill_id = data.get("profiles", {}).get(profile, {}).get("skillId", "")
    if not skill_id:
        sys.exit(f"Error: skillId not found for profile {profile} in ask-resources.json")
    return skill_id


def get_token_proxy_url(aws_profile: str) -> str:
    out = run([
        "aws", "cloudformation", "describe-stacks",
        "--stack-name", STACK_NAME,
        "--region", REGION,
        "--profile", aws_profile,
        "--query", "Stacks[0].Outputs[?OutputKey=='TokenProxyUrl'].OutputValue",
        "--output", "text",
    ])
    url = out.strip()
    if not url or url == "None":
        sys.exit(
            f"Error: TokenProxyUrl not found in stack '{STACK_NAME}'.\n"
            "Run 'sam deploy' first."
        )
    return url


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ENVS:
        sys.exit(
            "Usage: ./scripts/setup_account_linking.py dev | prd\n"
            "  dev: halhorn-dev profile\n"
            "  prd: halhorn-prd profile"
        )

    env = ENVS[sys.argv[1]]
    load_dotenv()

    client_id = os.environ.get("TESLA_CLIENT_ID", "")
    client_secret = os.environ.get("TESLA_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        sys.exit("Error: TESLA_CLIENT_ID and TESLA_CLIENT_SECRET must be set in .env")

    profile = env["profile"]
    skill_id = get_skill_id(profile)
    token_proxy_url = get_token_proxy_url(env["aws_profile"])

    print(f"Setting up Account Linking for [{sys.argv[1]}]...")
    print(f"  Skill ID:        {skill_id}")
    print(f"  Token Proxy URL: {token_proxy_url}")
    print(f"  Client ID:       {client_id}")
    print(f"  Auth URL:        {TESLA_AUTH_URL}")
    print(f"  Scopes:          {' '.join(SCOPES)}")

    account_linking = {
        "type": "AUTH_CODE",
        "authorizationUrl": TESLA_AUTH_URL,
        "authorizationUrlsByPlatform": [
            {"platformType": "iOS", "platformAuthorizationUrl": TESLA_AUTH_URL},
            {"platformType": "Android", "platformAuthorizationUrl": TESLA_AUTH_URL},
        ],
        "accessTokenUrl": token_proxy_url,
        "accessTokenScheme": "HTTP_BASIC",
        "clientId": client_id,
        "clientSecret": client_secret,
        "scopes": SCOPES,
        "domains": [],
    }

    account_linking_json = json.dumps({"accountLinkingRequest": account_linking})

    run([
        "ask", "smapi", "update-account-linking-info",
        "-s", skill_id,
        "-g", "development",
        "-p", profile,
        "--account-linking-request", account_linking_json,
    ])

    print("\n✅ Account Linking configured successfully!")

    out = run([
        "ask", "smapi", "get-account-linking-info",
        "-s", skill_id, "-g", "development", "-p", profile,
    ])
    info = json.loads(out)
    redirect_urls = info.get("accountLinkingResponse", {}).get("redirectUrls", [])

    if redirect_urls:
        print("\nRedirect URLs (Tesla Developer Portal に登録が必要):")
        for url in redirect_urls:
            print(f"  {url}")
    else:
        print("\nNote: Redirect URLs は更新直後は表示されないことがあります。")
        print("Alexa Developer Console の Account Linking セクションで確認してください。")
        print("（初回設定時は以下が表示されます）")
        print("  https://pitangui.amazon.com/api/skill/link/XXXXXX")
        print("  https://layla.amazon.com/api/skill/link/XXXXXX")
        print("  https://alexa.amazon.co.jp/api/skill/link/XXXXXX")


if __name__ == "__main__":
    main()
