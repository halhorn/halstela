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

### 3. 車両にバーチャルキーを登録する（初回のみ）

エアコン起動などの車両コマンドは Tesla Vehicle Command Protocol に対応しており、アプリの秘密鍵で署名して送信する。車両がその署名を検証できるよう、公開鍵を車両に登録（ペアリング）しておく必要がある。これを行わないとコマンド送信時に `UnknownKeyId`（Vehicle did not recognize the key）エラーになる。

前提として、公開鍵が Developer Portal に登録するドメイン上で配信されていること（`https://halhorn.github.io/.well-known/appspecific/com.tesla.3p.public-key.pem`）。

登録は Tesla モバイルアプリのディープリンクで行う。

1. 対象車両のオーナーでログイン済みの Tesla アプリが入ったスマートフォンを用意する
2. スマートフォンで次の URL を開く

   ```
   https://tesla.com/_ak/halhorn.github.io
   ```

3. Tesla アプリが起動し、バーチャルキー追加の確認が表示されるので承認する

承認後、アプリの「ロック → キー」一覧に追加された鍵が表示される。この登録は一度行えば有効で、車両から離れていても実行できる（BLE や車内タッチスクリーン操作は不要）。

### 4. エアコンを起動する

```bash
uv run python scripts/start_air_conditioning.py
```

車両がスリープ中の場合は自動で wake_up してからコマンドを送信する（最大 60 秒待機）。

コマンドは秘密鍵（`secret/private.pem`）で署名して送信される。`UnknownKeyId` エラーが出る場合は手順 3 のバーチャルキー登録が未完了なので、先にそちらを行う。

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
