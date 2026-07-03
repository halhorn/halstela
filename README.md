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

## デプロイ環境のセットアップ（初回のみ）

デプロイには AWS プロファイル・ASK CLI プロファイル・SSM パラメータの準備が必要。DEV/PRD は別 AWS アカウントのため、それぞれ `halhorn-dev` / `halhorn-prd` という名前で用意する（`scripts/deploy` がこの名前を参照する）。以下は DEV の例。

### 1. AWS プロファイル

デプロイ先リージョンは `us-west-2`。

```bash
aws configure --profile halhorn-dev
# Access Key / Secret を入力、region は us-west-2
aws sts get-caller-identity --profile halhorn-dev  # 対象アカウントか確認
```

### 2. ASK CLI プロファイル（Alexa スキル反映用）

```bash
npm install -g ask-cli          # 未インストールなら
ask configure --profile halhorn-dev
```

ブラウザで **スキルを所有する Amazon 開発者アカウント**にログインすること。別アカウントでログインすると `There is no Vendor ID associated with your account` や以降の SMAPI 呼び出しで `401` になる。ブラウザに別アカウントのセッションが残っている場合は、一度ログアウトしてから実行する。

設定できたか確認：

```bash
ask smapi list-skills-for-vendor -p halhorn-dev   # スキル一覧が返れば OK
```

### 3. SSM パラメータ

秘密情報（Tesla Client ID/Secret、署名用秘密鍵、Alexa Skill ID）は SSM Parameter Store（`/halstela/*`）に置く。ダミー値で枠を作成後、実値で上書きする。

```bash
./scripts/setup_ssm.py dev    # ダミー値でパラメータ作成（既存はスキップ）

# 実値で上書き（--profile halhorn-dev / --region us-west-2）
aws ssm put-parameter --name /halstela/tesla-client-id \
  --type SecureString --value 'REAL_VALUE' --overwrite \
  --region us-west-2 --profile halhorn-dev
# tesla-client-secret も同様

# 署名用秘密鍵はファイルから登録
aws ssm put-parameter --name /halstela/tesla-private-key \
  --type SecureString --value "$(cat secret/private.pem)" --overwrite \
  --region us-west-2 --profile halhorn-dev
```

Lambda は起動時に SSM から秘密鍵を読み込み、Vehicle Command Protocol の署名に使う。`tesla-private-key` が未登録だと署名できず、車両コマンドが失敗する。

### 4. `.env` の Lambda ARN

`scripts/deploy_skill.py` がスキル定義に埋め込む Lambda ARN を `.env` に設定する（`HALSTELA_DEV_LAMBDA_ARN` / `HALSTELA_PRD_LAMBDA_ARN`）。初回は `./scripts/deploy dev` の SAM デプロイ後に出力される ARN を控えて記入する。

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

## トラブルシューティング

- **`Failed to spawn: sam` / `No such file or directory`**: プロジェクトディレクトリを移動すると `.venv` 内の console-script（`sam` 等）の shebang が旧パスを指したままになり起動できなくなる。`rm -rf .venv && uv sync --all-extras` で venv を作り直す。
- **`ask` で `There is no Vendor ID` または SMAPI が `401`**: `ask configure` のログインがスキル所有アカウントと異なる。ブラウザで Amazon からログアウトし、正しいアカウントで `ask configure --profile halhorn-dev` をやり直す。
- **車両コマンドが `UnknownKeyId` で失敗**: バーチャルキーが車両に未登録。「スクリプトで動作確認する」手順 3 を参照。
- **`unauthorized_client: The 'client_id' parameter was not provided`**: OAuth トークン更新時のエラー。`.env` の `TESLA_CLIENT_ID` / `TESLA_CLIENT_SECRET` が設定されているか確認する。
