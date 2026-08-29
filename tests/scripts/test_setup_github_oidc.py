"""setup_github_oidc.py の信頼ポリシー / デプロイ権限の不変条件。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "setup_github_oidc.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("setup_github_oidc", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def oidc() -> Any:
    return _load_module()


def test_trust_policy_limits_to_main_of_this_repo(oidc: Any) -> None:
    policy = oidc.build_trust_policy("123456789012")
    statement = policy["Statement"][0]
    condition = statement["Condition"]["StringEquals"]

    assert statement["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert (
        statement["Principal"]["Federated"]
        == "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
    )
    assert condition["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    assert (
        condition["token.actions.githubusercontent.com:sub"]
        == "repo:halhorn/halstela:ref:refs/heads/main"
    )


def test_deploy_policy_is_not_administrator_access(oidc: Any) -> None:
    policy = oidc.deploy_policy("123456789012", "us-west-2")
    actions: list[str] = []
    for statement in policy["Statement"]:
        action = statement["Action"]
        if isinstance(action, str):
            actions.append(action)
        else:
            actions.extend(action)

    assert "*" not in actions
    assert "AdministratorAccess" not in actions
    joined = " ".join(actions)
    assert "cloudformation:" in joined
    assert "lambda:" in joined
    assert "s3:" in joined
    assert "iam:" in joined
    assert "ssm:GetParameter" in joined
    assert "logs:" in joined


def test_pass_role_is_limited_to_lambda(oidc: Any) -> None:
    policy = oidc.deploy_policy("123456789012", "us-west-2")
    pass_role = next(s for s in policy["Statement"] if s["Sid"] == "IamPassRoleToLambda")

    assert pass_role["Action"] == "iam:PassRole"
    assert pass_role["Resource"] == "arn:aws:iam::123456789012:role/halstela-*"
    assert pass_role["Condition"]["StringEquals"]["iam:PassedToService"] == "lambda.amazonaws.com"


def test_resources_are_scoped_to_halstela_and_sam(oidc: Any) -> None:
    policy = oidc.deploy_policy("123456789012", "us-west-2")
    by_sid = {s["Sid"]: s for s in policy["Statement"]}

    assert "stack/halstela/" in by_sid["CloudFormationStack"]["Resource"][0]
    assert by_sid["LambdaHalstela"]["Resource"][0].endswith(":function:halstela-*")
    assert "/halstela/*" in by_sid["SsmReadHalstela"]["Resource"]
    s3_resources = by_sid["S3SamArtifacts"]["Resource"]
    assert any("aws-sam-cli-managed-" in r for r in s3_resources)


def test_sam_transform_changeset_is_allowed(oidc: Any) -> None:
    policy = oidc.deploy_policy("123456789012", "us-west-2")
    stmt = next(s for s in policy["Statement"] if s["Sid"] == "SamTransform")

    assert stmt["Action"] == "cloudformation:CreateChangeSet"
    assert (
        stmt["Resource"] == "arn:aws:cloudformation:us-west-2:aws:transform/Serverless-2016-10-31"
    )
