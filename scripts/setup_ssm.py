#!/usr/bin/env python3
"""SSM Parameter Store の初期セットアップ。

ダミー値でパラメータを作成する。既存のパラメータは上書きしない。
実際の値は AWS Console または aws ssm put-parameter --overwrite で設定する。

用法: ./scripts/setup_ssm.py dev | prd
"""

import subprocess
import sys

PARAMS: list[dict[str, str]] = [
    {"name": "/halstela/tesla-client-id", "type": "SecureString", "dummy": "CHANGE_ME_client_id"},
    {"name": "/halstela/tesla-client-secret", "type": "SecureString", "dummy": "CHANGE_ME_client_secret"},
    {"name": "/halstela/alexa-skill-id", "type": "String", "dummy": "amzn1.ask.skill.CHANGE_ME"},
]

REGION = "us-west-2"

ENVS = {
    "dev": "halhorn-dev",
    "prd": "halhorn-prd",
}


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ENVS:
        sys.exit("Usage: ./scripts/setup_ssm.py dev | prd")

    env_name = sys.argv[1]
    profile = ENVS[env_name]

    print(f"Creating SSM parameters for [{env_name}] (profile: {profile})")
    print(f"  Region: {REGION}")
    print()

    for param in PARAMS:
        result = subprocess.run(
            [
                "aws", "ssm", "put-parameter",
                "--name", param["name"],
                "--type", param["type"],
                "--value", param["dummy"],
                "--region", REGION,
                "--profile", profile,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"  Created: {param['name']} ({param['type']})")
        elif "ParameterAlreadyExists" in result.stderr:
            print(f"  Exists:  {param['name']} (skipped)")
        else:
            print(f"  ERROR:   {param['name']}")
            print(f"           {result.stderr.strip()}")
            sys.exit(1)

    print()
    print("Done. Update values with:")
    print(f"  aws ssm put-parameter --name /halstela/tesla-client-id \\")
    print("    --type SecureString --value 'REAL_VALUE' --overwrite \\")
    print(f"    --region {REGION} --profile {profile}")


if __name__ == "__main__":
    main()
