# halstela

Tesla 車両を Alexa Smart Home スキルから操作するためのプロジェクト。車内温度の確認やエアコンの ON/OFF を音声で行える。

## 前提条件

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- AWS CLI（`aws` コマンド）+ プロファイル設定済み
- ASK CLI（`npm install -g ask-cli`）+ プロファイル設定済み
- Tesla Developer Portal でアプリケーション登録済み

## セットアップ

```bash
uv sync --all-extras
cp .env.example .env
# .env に Tesla Client ID / Secret、Lambda ARN を記入
```

## プロジェクト構成

```
halstela/             # 共有パッケージ（Tesla API クライアント、モデル等）
functions/
  skill/              # Alexa Smart Home Lambda ハンドラー
  token_proxy/        # OAuth トークン交換プロキシ Lambda
skill-package/        # Alexa スキル定義（skill.json）
layers/shared/        # Lambda Layer（halstela パッケージ + 依存）
scripts/              # デプロイ・ユーティリティスクリプト
template.yaml         # SAM テンプレート
```

## テスト・Lint

```bash
uv run pytest
uv run ruff check .
uv run mypy halstela
```

## デプロイ

Lambda（SAM）と Alexa スキル定義をまとめてデプロイする。

```bash
./scripts/deploy dev   # DEV 環境
./scripts/deploy prd   # PRD 環境
```

内部で以下を順に実行する：

1. `uv run sam build` + `uv run sam deploy` — Lambda / Layer を AWS にデプロイ
2. CloudFormation Outputs から Lambda ARN を取得
3. `ask smapi update-skill-manifest` — スキル定義（エンドポイント含む）を Alexa に反映

スキル定義のみ再デプロイしたい場合は `./scripts/deploy_skill.py dev` を単独で実行できる（`.env` の `HALSTELA_DEV_LAMBDA_ARN` を参照）。
