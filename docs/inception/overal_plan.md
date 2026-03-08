# 全体プラン: Tesla × Alexa 連携プロジェクト

## ゴール

Alexa 経由でテスラを操作できるようにする。

### 初期スコープ

- Alexa 経由で車内・外気温を確認する
- Alexa 経由でエアコンを ON にする

### 最終スコープ

- 様々な車両操作を Alexa から実行可能にする
- Alexa Skills として公開する

## 決定事項

| 項目 | 決定 |
|------|------|
| ホスティング | AWS Lambda（Alexa 直接呼び出し） |
| 認証方式 | Alexa Account Linking |
| 対象リージョン | 日本（ja-JP） |
| 開発言語 | Python |
| ユーザー範囲 | まず個人利用 → Alexa Skills 公開 |
| スキル種類 | Smart Home Skill（将来 Custom Skill 併用も検討） |

## プロジェクトフェーズ

### Phase 1: 計画（inception）

1. **全体プラン策定** ← 本ドキュメント
2. **ユーザーストーリー洗い出し** → `user_stories.md`
   - エピック・ユーザーストーリーを定義
   - 優先順位づけ
   - スキル種類（Custom Skill / Smart Home Skill）を決定

### Phase 2: 設計（construction）

3. **インフラ・アーキテクチャ設計** → `architecture.md`
   - AWS 構成（Lambda, Account Linking 等）
   - Tesla API との接続方式
   - デプロイ方式
4. **クラス設計** → `classes.md`
   - Lambda ハンドラー構成
   - 既存 `halstela` パッケージとの統合方針
   - モジュール・クラス設計

### Phase 3: 実装

5. **環境セットアップ**
   - Amazon Developer アカウント作成
   - AWS アカウント作成
   - Alexa スキル作成・設定
6. **初期スコープの実装**
   - バッテリー状態取得
   - エアコン ON
7. **テスト・デプロイ**
8. **機能拡張**（ユーザーストーリーに基づく）

## 現状の資産

`halstela` パッケージに以下が実装済み：

- Tesla OAuth2 認証フロー
- Tesla Fleet API HTTP クライアント
- 車両データ取得（バッテリー状態含む）
- トークン管理

---

## AI 向け詳細コンテキスト

### 既存リポジトリ構成

```
halstela/
├── halstela/          # メインパッケージ
│   ├── config.py      # TeslaConfig（pydantic-settings）
│   ├── http_client.py # TeslaHTTPClient（httpx ベース、同期）
│   ├── oauth.py       # TeslaOAuth2（authlib）
│   ├── oauth_callback_server.py  # ローカル OAuth コールバック
│   └── token.py       # TokenManager（JSON ファイル保存）
├── scripts/           # CLI スクリプト
│   ├── get_vehicle_data.py   # 車両データ取得（wake_up 対応）
│   ├── oauth_token.py        # OAuth トークン取得/更新
│   └── register_partner.py   # Partner 登録
├── .well-known/       # Tesla Partner 公開鍵
├── mdc/               # プロジェクトドキュメント
│   ├── inception/     # 計画ドキュメント
│   └── construction/  # 設計・実装ドキュメント
└── pyproject.toml     # 依存: authlib, httpx, pydantic, pydantic-settings
```

### 技術的考慮事項

- 既存の HTTP クライアントは `httpx` ベースの同期実装。Lambda でもそのまま利用可能
- Account Linking 採用のため、Alexa がユーザーの Tesla OAuth トークンを管理する。Lambda はリクエストごとに Alexa から渡されるアクセストークンを使う
- 現在の `TokenManager`（ファイルベース）は Lambda 環境では不要になる可能性がある
- Tesla API は車両が sleep 状態の場合 `wake_up` → ポーリングが必要（既存の `get_vehicle_data.py` に実装済み）
- Tesla Fleet API のエンドポイント一覧は `mdc/tesla-fleet-api-list.mdc` に整理済み
- エアコン ON: `POST /api/1/vehicles/{vehicle_id}/command/auto_conditioning_start`
- 車内温度: `GET /api/1/vehicles/{vehicle_id}/vehicle_data?endpoints=climate_state` → `inside_temp`, `outside_temp`
