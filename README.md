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

## スクリプトで動作確認する

### 1. Tesla OAuth トークンを取得する

初回は認可フローを実行する。ブラウザが開くので Tesla アカウントでログインし、権限を許可する。

```bash
uv run python scripts/oauth_token.py
```

トークンは `secret/token.json` に保存される。次回以降はリフレッシュトークンで更新できる。

```bash
uv run python scripts/oauth_token.py --refresh
```

### 2. 車両情報を取得する

```bash
uv run python scripts/get_vehicle_data.py
```

バッテリー残量・車内外温度・充電状態・車両設定などが JSON で出力される。

複数台所有している場合は環境変数で対象 VIN を指定できる。

```bash
TESLA_TARGET_VIN=LRWYHCFJ7SC307595 uv run python scripts/get_vehicle_data.py
```

### 3. エアコンを起動する

```bash
uv run python scripts/start_air_conditioning.py
```

車両がスリープ中の場合は自動で wake_up してからコマンドを送信する（最大 60 秒待機）。

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
