#!/usr/bin/env python3
"""GitHub Actions 用 OIDC プロバイダとデプロイ Role を作成する。

GitHub が長期キーなしで AWS を AssumeRole できるようにする（初回のみ、冪等）。

用法: ./scripts/setup_github_oidc.py dev

作成後、出力された Role ARN を GitHub リポジトリ変数 AWS_ROLE_ARN に登録する:
  gh variable set AWS_ROLE_ARN --body '<Role ARN>' --repo halhorn/halstela
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

REGION = "us-west-2"
ROLE_NAME = "halstela-gha-deploy"
POLICY_NAME = "sam-deploy"
STACK_NAME = "halstela"
GITHUB_REPO = "halhorn/halstela"
GITHUB_REF = "refs/heads/main"
OIDC_URL = "https://token.actions.githubusercontent.com"
OIDC_HOST = "token.actions.githubusercontent.com"
OIDC_AUDIENCE = "sts.amazonaws.com"
# GitHub OIDC では AWS が thumbprint を検証しないためプレースホルダでよい。
OIDC_THUMBPRINT = "ffffffffffffffffffffffffffffffffffffffff"

ENVS = {
    "dev": "halhorn-dev",
}


def build_trust_policy(account_id: str) -> dict[str, Any]:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": oidc_provider_arn(account_id)},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        f"{OIDC_HOST}:aud": OIDC_AUDIENCE,
                        f"{OIDC_HOST}:sub": f"repo:{GITHUB_REPO}:ref:{GITHUB_REF}",
                    }
                },
            }
        ],
    }


def deploy_policy(account_id: str, region: str) -> dict[str, Any]:
    stack_arn = f"arn:aws:cloudformation:{region}:{account_id}:stack/{STACK_NAME}/*"
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "CloudFormationStack",
                "Effect": "Allow",
                "Action": "cloudformation:*",
                "Resource": [
                    stack_arn,
                    f"arn:aws:cloudformation:{region}:{account_id}:changeSet/*",
                ],
            },
            {
                "Sid": "CloudFormationDescribe",
                "Effect": "Allow",
                "Action": [
                    "cloudformation:ListStacks",
                    "cloudformation:DescribeStacks",
                    "cloudformation:GetTemplateSummary",
                    "cloudformation:ValidateTemplate",
                ],
                "Resource": "*",
            },
            {
                "Sid": "S3SamArtifacts",
                "Effect": "Allow",
                "Action": "s3:*",
                "Resource": [
                    "arn:aws:s3:::aws-sam-cli-managed-*",
                    "arn:aws:s3:::aws-sam-cli-managed-*/*",
                    f"arn:aws:s3:::aws-sam-cli-*-{region}-*",
                    f"arn:aws:s3:::aws-sam-cli-*-{region}-*/*",
                ],
            },
            {
                "Sid": "S3ListBuckets",
                "Effect": "Allow",
                "Action": "s3:ListAllMyBuckets",
                "Resource": "*",
            },
            {
                "Sid": "LambdaHalstela",
                "Effect": "Allow",
                "Action": "lambda:*",
                "Resource": [
                    f"arn:aws:lambda:{region}:{account_id}:function:halstela-*",
                    f"arn:aws:lambda:{region}:{account_id}:function:halstela-*:*",
                    f"arn:aws:lambda:{region}:{account_id}:layer:halstela-*",
                    f"arn:aws:lambda:{region}:{account_id}:layer:halstela-*:*",
                ],
            },
            {
                "Sid": "IamHalstelaRoles",
                "Effect": "Allow",
                "Action": [
                    "iam:AttachRolePolicy",
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:DeleteRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:GetRole",
                    "iam:GetRolePolicy",
                    "iam:ListAttachedRolePolicies",
                    "iam:ListRolePolicies",
                    "iam:PutRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:UpdateAssumeRolePolicy",
                ],
                "Resource": f"arn:aws:iam::{account_id}:role/halstela-*",
            },
            {
                "Sid": "IamPassRoleToLambda",
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": f"arn:aws:iam::{account_id}:role/halstela-*",
                "Condition": {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}},
            },
            {
                "Sid": "IamReadManagedPolicies",
                "Effect": "Allow",
                "Action": ["iam:GetPolicy", "iam:GetPolicyVersion"],
                "Resource": "arn:aws:iam::aws:policy/*",
            },
            {
                "Sid": "SsmReadHalstela",
                "Effect": "Allow",
                "Action": ["ssm:GetParameter", "ssm:GetParameters"],
                "Resource": f"arn:aws:ssm:{region}:{account_id}:parameter/halstela/*",
            },
            {
                "Sid": "LogsHalstela",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:DescribeLogGroups",
                    "logs:PutRetentionPolicy",
                    "logs:TagResource",
                    "logs:UntagResource",
                ],
                "Resource": [
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/lambda/halstela-*",
                    f"arn:aws:logs:{region}:{account_id}:log-group:/aws/lambda/halstela-*:*",
                ],
            },
        ],
    }


def oidc_provider_arn(account_id: str) -> str:
    return f"arn:aws:iam::{account_id}:oidc-provider/{OIDC_HOST}"


def run_aws(
    profile: str, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    cmd = ["aws", *args, "--profile", profile]
    env = {**os.environ, "AWS_PAGER": ""}
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        print(result.stdout, file=sys.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result


def get_account_id(profile: str) -> str:
    result = run_aws(profile, ["sts", "get-caller-identity", "--output", "json"])
    data = json.loads(result.stdout)
    account_id = data.get("Account", "")
    if not account_id:
        sys.exit("Error: could not determine AWS account ID")
    return str(account_id)


def ensure_oidc_provider(profile: str, account_id: str) -> str:
    arn = oidc_provider_arn(account_id)
    got = run_aws(
        profile,
        [
            "iam",
            "get-open-id-connect-provider",
            "--open-id-connect-provider-arn",
            arn,
            "--output",
            "json",
        ],
        check=False,
    )
    if got.returncode == 0:
        client_ids = json.loads(got.stdout).get("ClientIDList", [])
        if OIDC_AUDIENCE not in client_ids:
            run_aws(
                profile,
                [
                    "iam",
                    "add-client-id-to-open-id-connect-provider",
                    "--open-id-connect-provider-arn",
                    arn,
                    "--client-id",
                    OIDC_AUDIENCE,
                ],
            )
            print(f"  Updated: OIDC provider client IDs ({OIDC_AUDIENCE})")
        else:
            print(f"  Exists:  OIDC provider {OIDC_HOST}")
        return arn

    created = run_aws(
        profile,
        [
            "iam",
            "create-open-id-connect-provider",
            "--url",
            OIDC_URL,
            "--client-id-list",
            OIDC_AUDIENCE,
            "--thumbprint-list",
            OIDC_THUMBPRINT,
            "--output",
            "json",
        ],
        check=False,
    )
    if created.returncode != 0 and "EntityAlreadyExists" not in created.stderr:
        print(created.stdout, file=sys.stdout)
        print(created.stderr, file=sys.stderr)
        sys.exit(created.returncode)
    print(f"  Created: OIDC provider {OIDC_HOST}")
    return arn


def ensure_role(profile: str, account_id: str) -> str:
    document = json.dumps(build_trust_policy(account_id))
    created = run_aws(
        profile,
        [
            "iam",
            "create-role",
            "--role-name",
            ROLE_NAME,
            "--assume-role-policy-document",
            document,
            "--description",
            "GitHub Actions OIDC role for SAM deploy (halstela)",
            "--output",
            "json",
        ],
        check=False,
    )
    if created.returncode == 0:
        print(f"  Created: role {ROLE_NAME}")
        arn = json.loads(created.stdout)["Role"]["Arn"]
    elif "EntityAlreadyExists" in created.stderr:
        run_aws(
            profile,
            [
                "iam",
                "update-assume-role-policy",
                "--role-name",
                ROLE_NAME,
                "--policy-document",
                document,
            ],
        )
        print(f"  Exists:  role {ROLE_NAME} (trust policy updated)")
        got = run_aws(profile, ["iam", "get-role", "--role-name", ROLE_NAME, "--output", "json"])
        arn = json.loads(got.stdout)["Role"]["Arn"]
    else:
        print(created.stdout, file=sys.stdout)
        print(created.stderr, file=sys.stderr)
        sys.exit(created.returncode)
    return str(arn)


def put_deploy_policy(profile: str, account_id: str) -> None:
    document = json.dumps(deploy_policy(account_id, REGION))
    run_aws(
        profile,
        [
            "iam",
            "put-role-policy",
            "--role-name",
            ROLE_NAME,
            "--policy-name",
            POLICY_NAME,
            "--policy-document",
            document,
        ],
    )
    print(f"  Put:     inline policy {POLICY_NAME}")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ENVS:
        sys.exit("Usage: ./scripts/setup_github_oidc.py dev")

    env_name = sys.argv[1]
    profile = ENVS[env_name]

    print(f"Setting up GitHub OIDC for [{env_name}] (profile: {profile})")
    print()

    account_id = get_account_id(profile)
    print(f"  Account: {account_id}")

    ensure_oidc_provider(profile, account_id)
    role_arn = ensure_role(profile, account_id)
    put_deploy_policy(profile, account_id)

    print()
    print(f"Role ARN: {role_arn}")
    print()
    print("Register as a GitHub Actions repository variable:")
    print(f"  gh variable set AWS_ROLE_ARN --body '{role_arn}' --repo {GITHUB_REPO}")


if __name__ == "__main__":
    main()
