#!/usr/bin/env bash
# DEV/PRD で Lambda ARN を切り替えて ask deploy する。
# 用法: ./scripts/deploy_skill.sh dev  または  ./scripts/deploy_skill.sh prd
# 要: .env に HALSTELA_DEV_LAMBDA_ARN / HALSTELA_PRD_LAMBDA_ARN を設定。

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_JSON="$REPO_ROOT/skill-package/skill.json"

if [[ -f "$REPO_ROOT/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.env"
  set +a
fi

ENV_NAME="${1:-}"
if [[ "$ENV_NAME" != "dev" && "$ENV_NAME" != "prd" ]]; then
  echo "Usage: $0 dev | prd"
  echo "  dev: use HALSTELA_DEV_LAMBDA_ARN, profile halhorn-dev"
  echo "  prd: use HALSTELA_PRD_LAMBDA_ARN, profile halhorn-prd"
  exit 1
fi

if [[ "$ENV_NAME" == "dev" ]]; then
  LAMBDA_ARN="${HALSTELA_DEV_LAMBDA_ARN:-}"
  PROFILE="halhorn-dev"
else
  LAMBDA_ARN="${HALSTELA_PRD_LAMBDA_ARN:-}"
  PROFILE="halhorn-prd"
fi

if [[ -z "$LAMBDA_ARN" ]]; then
  echo "Error: HALSTELA_${ENV_NAME^^}_LAMBDA_ARN is not set. Set it in .env or environment."
  exit 1
fi

# プレースホルダーを ARN に置換してから deploy（元の skill.json は退避して後で復元）
cp "$SKILL_JSON" "$SKILL_JSON.bak"
trap "mv '$SKILL_JSON.bak' '$SKILL_JSON'" EXIT

if sed --version 2>/dev/null | grep -q GNU; then
  sed -i "s|REPLACE_WITH_LAMBDA_ARN|$LAMBDA_ARN|g" "$SKILL_JSON"
else
  sed -i '' "s|REPLACE_WITH_LAMBDA_ARN|$LAMBDA_ARN|g" "$SKILL_JSON"
fi

cd "$REPO_ROOT"
ask deploy -p "$PROFILE"
