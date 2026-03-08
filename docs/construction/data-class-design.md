# データ・クラス設計: Tesla × Alexa 連携（E1〜E3）

## 前提

- アーキテクチャ設計: [arch-infra-design.md](./arch-infra-design.md)
- ユーザーストーリー: [user_stories.md](../inception/user_stories.md)

### 前提・既存資産

- **対象エピック**: E1（Account Linking）、E2（車内温度確認）、E3（エアコン操作）。E5 は将来拡張として考慮するが詳細設計はしない。
- **Lambda 構成**: Skill Lambda + Token Proxy Lambda の 2 本（分離構成、SAM でデプロイ）
- **言語・ランタイム**: Python 3.12
- **データクラス**: `dataclasses`（標準ライブラリ。pydantic は使わない）
- **スキル種類**: Smart Home Skill（将来 Custom Skill 併用も検討）
- **Skill Lambda フレームワーク**: 不要（Smart Home ディレクティブの JSON を直接処理）
- **Token Proxy Lambda**: フレームワーク不要（標準ライブラリ + httpx）
- **ライブラリ**: httpx, authlib
- **パッケージ管理**: uv（`pyproject.toml` + `uv.lock`）
- **IaC**: AWS SAM（`template.yaml`）
- **トークン管理**: Alexa Account Linking が担う。Lambda はリクエストごとに Alexa から渡される access_token を使用
- **車両 sleep 対応**: `wake_up` → ポーリングが必要（既存 `get_vehicle_data.py` の知見を流用）
- **既存コードの方針**: 既存実装にはとらわれず再設計する。ビジネスロジックはモデル層（共通モジュール）に集約し、Lambda ハンドラーと CLI スクリプトはモデル層を呼び出す薄いラッパーとする
- **テスト**: pytest でユニットテストを書く。CI（GitHub Actions）で自動実行する

#### 受け入れ条件
- [x] 前提が正確に記述されている

## デザインパターン

### 候補比較

| パターン | 概要 | メリット | デメリット |
|---|---|---|---|
| シンプルレイヤード | Handler → Service → Client の 3 層 | シンプル、小規模に最適、学習コスト低 | レイヤー境界が曖昧になりがち |
| ヘキサゴナル（AWS 推奨） | domain / ports / adapters で依存逆転。[AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/structure-a-python-project-in-hexagonal-architecture-using-aws-lambda.html) にて Python Lambda 向けのリファレンスあり | テスタビリティ高、AWS 公式パターン | この規模では過剰。port/adapter のファイル数が多くなる |
| クリーンアーキテクチャ | UseCase / Entity / Repository / Gateway で依存逆転 | 依存方向が厳密 | ヘキサゴナルと同様に過剰 |

### コード共有方式

2 つの Lambda 間で共通コード（Tesla API クライアント、ビジネスロジック）を共有する方式：

| 方式 | 概要 | メリット | デメリット |
|---|---|---|---|
| Lambda Layer | 共通コードを Layer としてパッケージし、両 Lambda から参照 | AWS 推奨。デプロイサイズ削減。関心の分離が明確 | Layer のビルド・バージョン管理が追加される |
| 各 Lambda にコピー | `sam build` 時に共通パッケージを各 Lambda に含める | シンプル。Layer の管理不要 | コードが重複する（ビルド時のみ、ソースは共有） |

### SAM ビルド方式

SAM の `BuildMethod: python-uv` は Lambda Function 向けの機能で、Lambda Layer には適用できない。本プロジェクトは Layer で共通コードを共有するため、Layer のビルドには `BuildMethod: makefile` を使用し、Makefile 内で `pip install ../../`（ルートの `pyproject.toml` を参照）することで依存管理を一元化する。

### 決定事項

- **採用パターン**: シンプルレイヤード（3 層構成）
  1. **Handler 層**: Lambda ハンドラー / CLI スクリプト（薄いラッパー）
  2. **Service 層**: ビジネスロジック（車両操作、データ取得、wake_up 制御など）
  3. **Client 層**: Tesla Fleet API との HTTP 通信
- **理由**: ヘキサゴナルは AWS 公式推奨だが、本プロジェクトの規模（外部依存は Tesla API のみ、DB なし、2 Lambda）では過剰
- **コード共有**: Lambda Layer で共通モジュール（Service 層 + Client 層）をパッケージし、両 Lambda から参照。将来の拡張性を考慮し Layer 方式を採用
- **Layer ビルド**: `BuildMethod: makefile`。Makefile 内で `pip install ../../ -t ...` を実行し、`pyproject.toml` の依存定義を参照（ライブラリの二重管理を防ぐ）
- Smart Home ディレクティブのディスパッチは Handler 層の中で行う（Service 層には影響しない）

#### 受け入れ条件
- [x] パターンがプロジェクト規模に適している

## DB スキーマ

該当なし。本プロジェクトは DB を使用しない（トークン管理は Alexa Account Linking、Lambda はステートレス）。

## API 設計

### Smart Home Skill ディレクティブ定義

Smart Home Skill として、Skill Lambda が処理するディレクティブ。テスラを1つの「エンドポイント（デバイス）」として Alexa に登録し、複数のインターフェースを持たせる。

#### デバイスディスカバリ

| ディレクティブ | 処理 |
|---|---|
| `Alexa.Discovery.Discover` | Tesla API で車両一覧を取得し、エンドポイント（デバイス）として返す |

#### 初期スコープ（E2〜E3）

| インターフェース | ディレクティブ | 発話例 | 対応ストーリー | Tesla API |
|---|---|---|---|---|
| `Alexa.TemperatureSensor` | `ReportState` | 「テスラの温度は？」 | E2-1 | `GET vehicle_data?endpoints=climate_state` → `inside_temp` |
| `Alexa.PowerController` | `TurnOn` | 「テスラのエアコンをつけて」 | E3-1 | `POST command/auto_conditioning_start` |

#### 将来拡張（E5）

| インターフェース | 用途 | 対応ストーリー |
|---|---|---|
| `Alexa.PowerController` | エアコン OFF | E3-2 |
| `Alexa.ThermostatController` | 温度設定 | E5 |
| `Alexa.LockController` | 施錠/解錠・状態確認 | E5 |
| `Alexa.ToggleController` | シートヒーター、セントリーモード等 | E5 |
| `Alexa.PowerController`（充電器デバイス） | 充電開始/停止 | E5 |

### Token Proxy Lambda

Lambda Function URL で公開する HTTPS エンドポイント。Alexa Account Linking のトークン交換を中継する。

| メソッド | パス | 処理 |
|---|---|---|
| `POST` | `/` (Function URL ルート) | Alexa からのトークン交換リクエストを受け取り、`audience` パラメータを付与して Tesla Token Endpoint に転送。レスポンスをそのまま返す |

リクエスト/レスポンス:
- **入力**: Alexa が送る標準 OAuth2 パラメータ（`grant_type`, `code` or `refresh_token`, `client_id`, `client_secret`, `redirect_uri`）
- **付与**: `audience=https://fleet-api.prd.na.vn.cloud.tesla.com`（リージョン固定）
- **出力**: Tesla Token Endpoint のレスポンスをそのまま返却（`access_token`, `refresh_token`, `expires_in` 等）

#### 受け入れ条件
- [x] ディレクティブがユーザーストーリー E2〜E3 を満たしている
- [x] Token Proxy の入出力が明確である

## クラス設計

### ディレクトリ構成

```
halstela/                          # Repository root
├── pyproject.toml                 # ルート: halstela パッケージ定義 + dev deps
├── template.yaml                  # SAM テンプレート
├── samconfig.toml                 # SAM デプロイ設定
│
├── halstela/                      # 共通パッケージ（→ Lambda Layer）
│   ├── __init__.py
│   ├── config.py                  # TeslaConfig（横断的設定）
│   ├── models/                    # データクラス（1 クラス 1 ファイル）
│   │   ├── vehicle.py             # Vehicle
│   │   ├── climate_state.py       # ClimateState
│   │   └── command_result.py      # CommandResult
│   ├── clients/                   # Client 層
│   │   └── tesla_fleet_client.py  # TeslaFleetClient, TeslaAPIError
│   ├── services/                  # Service 層
│   │   └── vehicle_service.py     # VehicleService
│   └── auth/                      # 認証関連（CLI 用）
│       ├── oauth.py               # TeslaOAuth2
│       ├── oauth_callback_server.py # OAuthCallbackServer
│       └── token.py               # TokenManager
│
├── functions/                     # Lambda ハンドラー（Handler 層）
│   ├── skill/
│   │   └── handler.py             # Smart Home ディレクティブ処理
│   └── token_proxy/
│       └── handler.py             # トークン交換プロキシ
│
├── scripts/                       # CLI スクリプト（Handler 層）
│   ├── get_vehicle_data.py
│   ├── oauth_token.py
│   └── register_partner.py
│
├── tests/                         # halstela/ と同じパス構成
│   ├── conftest.py                # 共通フィクスチャ
│   ├── halstela/
│   │   ├── models/
│   │   │   ├── test_vehicle.py
│   │   │   ├── test_climate_state.py
│   │   │   └── test_command_result.py
│   │   ├── clients/
│   │   │   └── test_tesla_fleet_client.py
│   │   └── services/
│   │       └── test_vehicle_service.py
│   └── functions/
│       ├── test_skill_handler.py
│       └── test_token_proxy_handler.py
│
├── .github/
│   └── workflows/
│       └── ci.yml                 # GitHub Actions CI
│
├── .well-known/                   # Tesla Partner 公開鍵（既存）
└── secret/                        # 秘密情報（gitignore）
```

### クラス/モジュール一覧

| レイヤー | モジュール | 責務 |
|---|---|---|
| **Client** | `halstela/clients/tesla_fleet_client.py` | Tesla Fleet API との HTTP 通信。低レベル API ラッパー |
| **Service** | `halstela/services/vehicle_service.py` | ビジネスロジック。wake_up 制御、データ変換、コマンド実行 |
| **Model** | `halstela/models/vehicle.py` | 車両データクラス |
| **Model** | `halstela/models/climate_state.py` | 気候状態データクラス |
| **Model** | `halstela/models/command_result.py` | コマンド実行結果データクラス |
| **Config** | `halstela/config.py` | 環境変数からの設定読み込み |
| **Auth** | `halstela/auth/oauth.py` | OAuth2 クライアント（CLI 用） |
| **Auth** | `halstela/auth/oauth_callback_server.py` | ローカルコールバックサーバー |
| **Auth** | `halstela/auth/token.py` | トークン保存・読み込み |
| **Handler** | `functions/skill/handler.py` | Smart Home ディレクティブのディスパッチ・レスポンス構築 |
| **Handler** | `functions/token_proxy/handler.py` | OAuth2 トークン交換の中継 |
| **Handler** | `scripts/*.py` | CLI 用の薄いラッパー |

### データ構造

#### Vehicle

| プロパティ | 型 | 説明 |
|---|---|---|
| id | str | 車両 ID（API 用） |
| vin | str | 車両識別番号 |
| display_name | str | 表示名（例: "My Tesla"） |
| state | str | 車両状態（"online", "asleep", "offline"） |

#### ClimateState

| プロパティ | 型 | 説明 |
|---|---|---|
| inside_temp | float \| None | 車内温度（℃） |
| outside_temp | float \| None | 外気温（℃） |
| is_climate_on | bool | エアコン動作中か |
| driver_temp_setting | float | 設定温度（℃） |

#### CommandResult

| プロパティ | 型 | 説明 |
|---|---|---|
| success | bool | コマンド成功/失敗 |
| reason | str | 結果メッセージ（例: "ok"） |

#### TeslaConfig

| プロパティ | 型 | 説明 |
|---|---|---|
| client_id | str | Tesla OAuth Client ID |
| client_secret | str | Tesla OAuth Client Secret |
| fleet_api_base_url | str | Fleet API ベース URL（デフォルト: NA リージョン） |
| token_endpoint | str | Tesla トークンエンドポイント URL |

| メソッド | 戻り値 | 説明 |
|---|---|---|
| from_env() | TeslaConfig | 環境変数から設定を読み込む（classmethod） |

#### TeslaFleetClient

コンストラクタ: `__init__(self, access_token: str, base_url: str)`

| メソッド | 戻り値 | 説明 |
|---|---|---|
| get_vehicles() | list[dict] | 車両一覧を取得 |
| get_vehicle_data(vehicle_id, endpoints) | dict | 車両データを取得（endpoints 指定） |
| send_command(vehicle_id, command, body?) | dict | 車両にコマンドを送信 |
| wake_up(vehicle_id) | dict | 車両を起動 |

#### VehicleService

コンストラクタ: `__init__(self, client: TeslaFleetClient)`

| メソッド | 戻り値 | 説明 |
|---|---|---|
| get_vehicles() | list[Vehicle] | 車両一覧を取得し Vehicle に変換 |
| get_climate_state(vehicle_id) | ClimateState | wake_up → climate_state 取得 → 変換 |
| start_air_conditioning(vehicle_id) | CommandResult | wake_up → エアコン ON |
| ensure_awake(vehicle_id) | None | wake_up + ポーリング（state が "online" になるまで） |

#### functions/skill/handler.py

| 関数 | 戻り値 | 説明 |
|---|---|---|
| lambda_handler(event, context) | dict | エントリポイント。namespace + name でディスパッチ |
| handle_discovery(directive) | dict | 車両をエンドポイントとして返す |
| handle_power_control(directive) | dict | TurnOn → エアコン ON |
| handle_report_state(directive) | dict | 温度をレポート |
| build_error_response(directive, error) | dict | エラーレスポンスを構築 |

#### functions/token_proxy/handler.py

| 関数 | 戻り値 | 説明 |
|---|---|---|
| lambda_handler(event, context) | dict | エントリポイント。POST body を解析して中継 |
| proxy_token_request(params) | dict | audience を付与して Tesla に転送、レスポンスを返却 |

### 依存関係

```
Handler 層                    Service 層                        Client 層
─────────────────────────     ───────────────────────────       ──────────────────────────────
functions/skill/handler.py ─→ services/vehicle_service.py ─→   clients/tesla_fleet_client.py ─→ Tesla Fleet API
functions/token_proxy/handler.py ─→ (直接 httpx で Tesla Token Endpoint に転送)
scripts/*.py ───────────────→ services/vehicle_service.py ─→   clients/tesla_fleet_client.py ─→ Tesla Fleet API

                              models/*（各層で共有、他モジュールに依存しない）
                              config.py（Handler 層・Client 層で使用）
                              auth/*（CLI スクリプト用の認証ユーティリティ）
```

- Handler → Service → Client の一方向依存。逆方向の依存はない
- `models/` は全層から参照されるが、他モジュールに依存しない。1 クラス 1 ファイルの原則に従う
- `auth/` は CLI スクリプト専用。Lambda からは参照しない
- Token Proxy Lambda は Service 層を使わず、直接 httpx で Tesla に転送（シンプルなプロキシのため）
- Lambda Layer には `halstela/` パッケージ + 依存ライブラリ（httpx, authlib）を含む

#### 受け入れ条件
- [x] 責務が明確に分離されている
- [x] 入出力のデータ構造が定義されている
- [x] 依存の方向が一方向である
