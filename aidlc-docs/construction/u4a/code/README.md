# U4a Code — token_issue / pool_ingest（+ 管理 API）生成サマリ

**ユニット**: U4a。**U1 コードへの追記**（Item.body・Repository 書込・entry.py 配線）を含む。
**生成日**: 2026-07-13（Code Generation Part 2）。実装規約は G-1 確定（raw workers API + Pydantic v2 / module-level `on_fetch` / CI デプロイ）。

---

## 1. 生成/変更ファイル

| 種別 | ファイル | 内容 |
|---|---|---|
| **U1 波及** | `schema/models.py` | `Item.body: str`（必須）追加、`body_ref` 任意化 |
| | `schema/__init__.py` | ペイロードモデル公開、`validate_item`（body 検証） |
| | `migrations/0002_item_body.sql` | items 再構築（body NOT NULL 追加・body_ref NULL 化） |
| | `backend/repo/repository.py` | `list_items` に body。**`insert_items`（upsert+凍結ガード）・`insert_tokens`・`referenced_item_ids`・`all_token_strings`** 追加 |
| **新規 schema** | `schema/payloads.py` | `ItemIngestRequest`/`IngestResult`/`RejectedItem`/`SufficiencyResult`/`TokenIssueRequest`/`TokenIssueResult` |
| **新規 domain** | `backend/domain/pool_sufficiency.py` | `pool_sufficiency`（三点セット・純粋・**単一実装**, DP-U4a-05） |
| **新規 admin** | `backend/admin/api.py` | AdminApi（`/admin/items`・`/admin/tokens`・統一封筒） |
| | `backend/admin/auth.py` | AuthGuard（Basic・定数時間比較・401） |
| | `backend/admin/log.py` | AdminLog（許可フィールド限定＝token/body 排除） |
| | `backend/entry.py` | `/admin/*` を AuthGuard→AdminApi に配線（単一チョークポイント） |
| **新規 scripts** | `scripts/pool_ingest.py`・`scripts/token_issue.py`・`scripts/_client.py` | pure-Python CLI（urllib, HTTPS+Basic, 環境変数認証） |
| **CI/構成** | `.github/workflows/deploy.yml` | 機能化（test→migrations→deploy, RT-1 CLOSE） |
| | `.gitignore` | 配布物（`*.dist.txt` 等）除外 |
| **テスト** | `tests/pbt/test_pool_sufficiency.py` | 三点セット・単調性・境界（PBT-03） |
| | `tests/unit/u1/test_schema.py` | body 必須・body_ref 任意（回帰） |
| | `tests/integration/`（it_entry.py / drive_u4a.py） | admin 越し PU4a-1/2/3a/3b/4/6 |

## 2. 主要な業務ロジック
- **段階投入対応**: pool_ingest は**マージ後プール**で充足判定し、未達でも **warning + 投入成功**（BR-U4a-05）。ハードゲートは token_issue（BR-U4a-12, 未達→発行拒否）。**両者が同一 `pool_sufficiency` を呼ぶ**（U4a-NFR-10）。
- **凍結ガード**: `pairs` 参照済み item への更新は拒否・投入全体中断（BR-U4a-03）。参照集合は batch 直前取得（窓最小化）。
- **冪等 upsert**: 未参照 item は `ON CONFLICT DO UPDATE`（body_ref None は SQL リテラル NULL で bind, D1_TYPE_ERROR 回避）。
- **認証**: `/admin/*` 単一チョークポイント・定数時間比較。**ログに token/body を出さない**（AdminLog が構造的に排除）。

## 3. テスト実行実績（2026-07-13）
- **unit + PBT**: `HYPOTHESIS_PROFILE=ci` で **27 passed**（U1 回帰 19 + pool_sufficiency 6 + schema 2）。U1 回帰（Item.body 追加）を全緑で維持。
- **integration（実 D1, miniflare）**: **全 7 シナリオ PASS**（`tests/integration/result-u4a-integration.json`）。PU4a-6 認証 401 / PU4a-3a 段階投入 warn / PU4a-1 冪等 / PU4a-3b 発行ゲート / ingest-realistic / PU4a-4 トークン発行 / PU4a-2 凍結ガード。
  - 副次確認: **migration 0001+0002 の適用順**（空 items で rebuild 成立）を実 D1 で検証。

## 4. CLI 使い方（手元/CI, Worker 外）
```bash
# 環境変数で認証（Worker 側 wrangler secret と同名）
export ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=...
# 刺激プール投入（段階投入可）
uv run python -m scripts.pool_ingest items.json --base-url https://<worker>.workers.dev
# トークン発行（充足ゲート通過で発行）
uv run python -m scripts.token_issue 30 --base-url https://<worker>.workers.dev \
    --url-template 'https://<worker>.workers.dev/s/{token}' --out tokens.dist.txt
```

## 5. RT-1 CLOSE
`deploy.yml` を機能化（test 前置ゲート → migrations apply --remote(0001+0002) → deploy、tee パイプ不使用で終了コード保持）。**RT-1（deploy.yml 肉付け）CLOSE**。実デプロイはユーザー環境（Cloudflare 認証）で、`ADMIN_BASIC_*` は手元 `wrangler secret put`。
