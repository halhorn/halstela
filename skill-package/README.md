# Alexa スキル定義（ASK CLI）

- **skill.json**: Smart Home スキルのマニフェスト。`REPLACE_WITH_LAMBDA_ARN` はデプロイ時に DEV/PRD の ARN に差し替える（手動または `scripts/deploy_skill.py`）。
- Smart Home スキルではインタラクションモデル（intents）は不要なため、`skill.json` のみでデプロイする。

## DEV / PRD で ARN を切り替える

1. **.env** に Lambda ARN を設定する。
   - `HALSTELA_DEV_LAMBDA_ARN`: DEV 用 Skill Lambda の ARN（`sam deploy` で取得）
   - `HALSTELA_PRD_LAMBDA_ARN`: PRD 用 Skill Lambda の ARN

2. **デプロイ**  
   - DEV: `./scripts/deploy_skill.py dev`  
   - PRD: `./scripts/deploy_skill.py prd`  

   スクリプトが `skill.json` 内の `REPLACE_WITH_LAMBDA_ARN` を該当 ARN に置換し、`ask smapi update-skill-manifest` で Alexa に反映する。`skill.json` 自体は変更されない（一時ファイルを使用）。

3. **手動で切り替える場合**  
   `skill-package/skill.json` の `REPLACE_WITH_LAMBDA_ARN` を該当環境の ARN に置換し、`ask smapi update-skill-manifest` で反映する。
