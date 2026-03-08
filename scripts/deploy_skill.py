#!/usr/bin/env python3
"""DEV/PRD で Lambda ARN を切り替えて skill manifest を Alexa に反映する。

ask deploy (パッケージインポート方式) は Smart Home エンドポイントの検証で
失敗するため、ask smapi update-skill-manifest を使用する。

用法: ./scripts/deploy_skill.py dev  または  ./scripts/deploy_skill.py prd
要:   .env に HALSTELA_DEV_LAMBDA_ARN / HALSTELA_PRD_LAMBDA_ARN を設定。
      ask-resources.json の各プロファイルに skillId が設定されていること。
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_JSON = REPO_ROOT / "skill-package" / "skill.json"
ASK_RESOURCES = REPO_ROOT / "ask-resources.json"
ENV_FILE = REPO_ROOT / ".env"

ENVS = {
    "dev": {"arn_key": "HALSTELA_DEV_LAMBDA_ARN", "profile": "halhorn-dev"},
    "prd": {"arn_key": "HALSTELA_PRD_LAMBDA_ARN", "profile": "halhorn-prd"},
}


def load_dotenv() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def get_skill_id(profile: str) -> str:
    data = json.loads(ASK_RESOURCES.read_text())
    skill_id = data.get("profiles", {}).get(profile, {}).get("skillId", "")
    if not skill_id:
        sys.exit(f"Error: skillId not found for profile {profile} in ask-resources.json")
    return skill_id


def replace_placeholder(obj: object, arn: str) -> object:
    if isinstance(obj, dict):
        return {k: replace_placeholder(v, arn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [replace_placeholder(v, arn) for v in obj]
    if obj == "REPLACE_WITH_LAMBDA_ARN":
        return arn
    return obj


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ENVS:
        sys.exit(
            "Usage: ./scripts/deploy_skill.py dev | prd\n"
            "  dev: use HALSTELA_DEV_LAMBDA_ARN, profile halhorn-dev\n"
            "  prd: use HALSTELA_PRD_LAMBDA_ARN, profile halhorn-prd"
        )

    env = ENVS[sys.argv[1]]
    load_dotenv()

    lambda_arn = os.environ.get(env["arn_key"], "")
    if not lambda_arn:
        sys.exit(f"Error: {env['arn_key']} is not set. Set it in .env or environment.")

    profile = env["profile"]
    skill_id = get_skill_id(profile)

    manifest = json.loads(SKILL_JSON.read_text())
    manifest = replace_placeholder(manifest, lambda_arn)

    print(f"Deploying skill manifest for profile [{profile}]...")
    print(f"  Skill ID: {skill_id}")
    print(f"  Lambda ARN: {lambda_arn}")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(manifest, f, ensure_ascii=False)
        tmppath = f.name

    try:
        run([
            "ask", "smapi", "update-skill-manifest",
            "-s", skill_id, "-g", "development", "-p", profile,
            "--manifest", f"file:{tmppath}",
        ])
    finally:
        os.unlink(tmppath)

    print("\nManifest update accepted. Waiting for build to complete...")

    for _ in range(12):
        time.sleep(5)
        out = run(["ask", "smapi", "get-skill-status", "-s", skill_id, "-p", profile])
        status = json.loads(out).get("manifest", {}).get("lastUpdateRequest", {}).get("status", "UNKNOWN")
        print(f"  Build status: {status}")

        if status == "SUCCEEDED":
            print("\nSkill manifest deployed successfully!")
            return
        if status == "FAILED":
            print(f"\nError: Skill manifest build failed.\n{out}")
            sys.exit(1)

    sys.exit(
        f"\nWarning: Build status polling timed out (60s). Check status manually:\n"
        f"  ask smapi get-skill-status -s {skill_id} -p {profile}"
    )


if __name__ == "__main__":
    main()
