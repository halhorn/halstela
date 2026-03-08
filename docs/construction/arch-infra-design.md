# アーキテクチャ・インフラ設計: Tesla × Alexa 連携（E1）

## 企画概要

テスラオーナー向けに、Alexa 経由でテスラを操作できる Alexa Smart Home Skill を構築する。
本ドキュメントではまず E1（Alexa とテスラを安全に連携する = Account Linking 基盤）を対象にアーキテクチャを設計し、E2・E3 の実装基盤を整える。

企画関連情報：
- [全体プラン](../inception/overal_plan.md)
- [ユーザーストーリー](../inception/user_stories.md)

### 前提・既存資産
- `halstela` パッケージに Tesla OAuth2 認証・Fleet API クライアント・車両データ取得が実装済み
- 決定済み事項（overal_plan.md より）：ホスティング = AWS Lambda、認証 = Alexa Account Linking、言語 = Python、リージョン = ja-JP

#### 受け入れ条件
- [x] 企画概要が正確に記述されている
- [x] 既存資産・決定事項が反映されている

## 全体アーキテクチャ

### データの流れ

```
【スキル呼び出し】
  Alexa デバイス → Alexa Service → Skill Lambda → Tesla Fleet API
                                    (access_token は Alexa が付与)

【Account Linking（初回連携）】
  Alexa アプリ → Tesla OAuth 認可画面（直接）→ ユーザー認証・同意
                                              → Alexa redirect_uri へリダイレクト
             → Alexa Service → Token Proxy Lambda → Tesla Token Endpoint
                               (audience を付与)     (access_token + refresh_token 返却)
             → Alexa がトークンを保存・管理

【トークンリフレッシュ】
  Alexa Service → Token Proxy Lambda → Tesla Token Endpoint
                  (audience を付与)
```

### コンポーネント

| コンポーネント | 役割 |
|---|---|
| Alexa Service | 音声認識・NLU・Smart Home ディレクティブ判定・Account Linking トークン管理 |
| Skill Lambda | Alexa からの Smart Home ディレクティブを処理し、Tesla Fleet API を呼ぶ |
| Token Proxy Lambda | Alexa → Tesla トークン交換を中継し、`audience` パラメータを追加する |
| Tesla OAuth Server | ユーザー認証・認可コード・トークン発行 |
| Tesla Fleet API | 車両データ取得・コマンド実行 |

### Token Proxy が必要な理由

Alexa Account Linking は標準 OAuth2 のトークン交換パラメータ（`grant_type`, `code`, `client_id`, `client_secret`, `redirect_uri`）のみを送信する。一方、Tesla Fleet API のトークンエンドポイントは `audience`（Fleet API リージョン URL）が**必須**。Alexa にカスタムパラメータを追加する手段がないため、中間にプロキシを置いて `audience` を付与する。

Token Proxy の実装：
- Lambda Function URL（HTTPS エンドポイント、API Gateway 不要でシンプル・無料）
- Alexa の Account Linking 設定で Access Token URI にこの URL を指定
- 認可 URL（Authorization URI）は Tesla のものを直接指定可能

### 使用するインフラ（AWS）

| サービス | 用途 |
|---|---|
| AWS Lambda × 2 | Skill Lambda + Token Proxy Lambda（分離構成） |
| Lambda Function URL | Token Proxy の HTTPS エンドポイント |
| CloudWatch Logs | ログ監視 |

### 決定事項

- **Lambda 構成**: 2 Lambda に分離（Skill Lambda / Token Proxy Lambda）。関心の分離を優先。
- **デプロイ方式**: AWS SAM（`sam deploy` でデプロイ、Lambda に特化したシンプルなテンプレート）
- **Alexa スキル定義**: ASK CLI で IaC 管理（後述）

### Alexa スキル定義の IaC（ASK CLI）

スキルのマニフェスト・インタラクションモデルは **ASK CLI**（[Alexa Skills Kit CLI](https://developer.amazon.com/en-US/docs/alexa/smapi/ask-cli-intro.html)）でコード管理し、`ask deploy` で Alexa 側に反映する。

- **役割分担**: AWS 側（Lambda・Token Proxy）は SAM でデプロイ。Alexa 側（スキル定義）は ASK CLI でリポジトリ管理し `ask deploy` で更新。Lambda は SAM（Python）のまま、スキル定義だけ ASK CLI で扱うハイブリッド構成。
- 設定ファイル・ディレクトリ構成・認証・Account Linking の扱いなど**具体的な構成は [data-class-design](./data-class-design.md) に記載する**。

### コスト概算
- 合計：**0 円/月**（AWS 無料枠内）
  - 想定リクエスト：個人利用のため 1日数回〜数十回（月 1,000 件未満）
- 詳細：
  - Lambda: 0 円/月（無料枠：100万リクエスト/月、40万GB秒/月）
    - https://aws.amazon.com/lambda/pricing/
  - Lambda Function URL: 0 円/月（Lambda の料金に含まれる）
  - CloudWatch Logs: 0 円/月（無料枠：5GB/月）
    - https://aws.amazon.com/cloudwatch/pricing/
  - S3（SAM デプロイ用）: 0 円/月（無料枠：5GB/月、パッケージは数 MB 程度）
    - https://aws.amazon.com/s3/pricing/
  - CloudFormation / SAM CLI: 無料

#### 受け入れ条件
- [x] データの流れとコンポーネントが明確である
- [x] Token Proxy の必要性と方式が合意されている
- [x] インフラ構成が決定している
- [x] コスト見積もりが妥当である

## 言語・フレームワーク

既存の `halstela` パッケージの構成に則り、新規に必要なものを追加する。

### サーバー（Lambda）

- **言語**: Python 3.12
- **Lambda ランタイム**: python3.12
- **データクラス**: `dataclasses`（標準ライブラリに統一。pydantic / pydantic-settings は削除）
  - 既存の `TeslaConfig`（pydantic-settings）は dataclass + `os.environ` に移行する
  - 理由：依存削減による Lambda コールドスタート改善、現状 pydantic の高度な機能を未使用
- **フレームワーク**:
  - Skill Lambda: フレームワーク不要（Smart Home Skill は Smart Home ディレクティブの JSON を直接処理する。`ask-sdk-core` は不要）
  - Token Proxy Lambda: フレームワーク不要（標準ライブラリ + httpx で十分）
- **既存ライブラリ（流用）**: httpx, authlib
- **パッケージ管理**: uv（`pyproject.toml` + `uv.lock`、既存に則る）
  - Lambda デプロイ時の依存パッケージングは SAM の uv ワークフロー（`sam build`）または `uv export` → `requirements.txt` 経由で行う
- **Linter**: ruff（既存に則る）
- **静的型検査**: mypy（既存に則る）
- **ユニットテスト**: pytest
- **IaC / デプロイ**: AWS 側は AWS SAM（`template.yaml`）。Alexa スキル定義は ASK CLI で管理し `ask deploy` でデプロイ（詳細は data-class-design 参照）。

### クライアント

なし（Alexa デバイスが UI を担う）

#### 受け入れ条件
- [x] 言語・ランタイムが決定している
- [x] 追加ライブラリが明確である
- [x] 開発ツールチェーンが決定している
