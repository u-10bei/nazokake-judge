# U2 Infrastructure Design — 参加者セッション（participant）

**ユニット**: U2。**U1/U4a の共有インフラ（D1 + schema/ + CI デプロイ）を流用**し、差分のみを定義する。共有分は `shared-infrastructure.md`、実装規約（F-1〜F-6）は U1 `infrastructure-design.md §2.1`、CI（`deploy.yml`）は U4a `infrastructure-design.md §5` を参照。
**方針**: 新規インフラは最小。差分は (a) **静的フロント配信＝Workers Static Assets（同一オリジン）**、(b) `/api/*` ルート追加、(c) CORS なし、(d) `migration 0003`（likert UNIQUE）、(e) `deploy.yml` は**無変更**（0003 は versioned 自動適用）。**参加者 API は新規シークレットなし**（トークン=資格, U2-NFR-01）。

---

## 1. LC-U2 → インフラ マッピング（差分）

| 論理コンポーネント | インフラ | 備考 |
|---|---|---|
| **LC-U2-08 ParticipantFrontend** | **Workers Static Assets**（`wrangler.toml` `[assets]` = `frontend/`）、同一 Worker・同一オリジン（Q1=A） | CORS 不要。`pywrangler deploy` がアセット同時アップロード |
| **LC-U2-01 ParticipantApi** | 既存 Worker に **`/api/*` ルート追加**（同一サブドメイン, Q2=A） | `on_fetch` 手動ディスパッチ。応答は `Cache-Control: no-store`（DP-U2-04） |
| **LC-U2-02/03/04 Services** | Worker 内 compute | インフラ依存なし（U1/U4a 公開面を消費） |
| **LC-U2-05 ViewSerializer** | Worker 内 compute（純粋・出自秘匿） | インフラ依存なし |
| **LC-U2-06 ParticipantLog** | Worker stdout（JSON）→ wrangler tail | トークンはハッシュ・本文は非出力（DP-U2-03） |
| **LC-U2-07 LikertSelector** | Worker 内 compute（純粋関数） | インフラ依存なし |
| **Repository 拡張 / D1** | 既存 **D1 バインディング（`DB`）** 経由 | **migration 0003** で `likert_responses` UNIQUE 追加 |

---

## 2. Compute / 静的配信（Q1 / Q2）

- **同一 Worker・同一オリジン**: 参加者フロント（`frontend/`）を **Workers Static Assets** で配信し、`/api/*` は同一 Worker の `on_fetch` が処理。証明書・デプロイを一本化。
- **ルーティング**: **`/api/*` は Worker（アセット非一致で Worker に到達）、それ以外は静的アセット**。
- **SPA フォールバック不使用（Q2=A 簡素化）**: 参加者は `/`（+ `?token=`）しか開かない（フェーズ駆動・クライアントルーティング/ディープリンクなし）。`not_found_handling`（index.html フォールバック）は**設定しない**。未知パスは 404 で構わない。→ assets/Worker の優先順位に beta の複雑さを足さない。
- **キャッシュ**: `/api/*` は Worker で `Cache-Control: no-store`（DP-U2-04）、静的アセットは既定キャッシュ（本文を含まないため可）。
- **`wrangler.toml` 追記（見込み・Code Generation 冒頭検証で確定）**:
  ```toml
  [assets]
  directory = "./frontend"
  # binding 名・run_worker_first 等の要否は §6 の beta 検証で確定
  ```

## 3. Networking / CORS（Q3）
- **同一オリジンゆえ CORS を設けない**（`/api/*` はブラウザから同一オリジンで呼ばれる）。HTTPS 強制（Cloudflare 既定）。
- 参加者 API は **Basic 認証なし・トークン=資格**（U2-NFR-01）。将来フロントを別オリジンに分離する場合のみ、許可オリジンをフロント配信元に限定した CORS を追加（現時点は不要）。

## 4. Secrets（差分なし）
- **参加者 API は新規シークレットなし**（トークン=資格）。`ADMIN_BASIC_*`（U4a）は管理 API 専用で U2 は使わない。`.dev.vars` への追加項目なし。

## 5. Storage — migration 0003（Q4）
- `migrations/0003_likert_unique.sql`（versioned）: `likert_responses` に **`UNIQUE(token, target_ref)`** 追加。**新規プロジェクトで既存行なし**のため安全。
- **適用順序を厳守**: `wrangler d1 migrations apply`（**dev→prod**）を **参加者 API デプロイより前**に（0002 と同じ流儀）。
- **`AssignmentParams.likert_fixed_targets`** は schema/ の追加（DDL 変更なし・アプリ層）。

## 6. CI/CD — `deploy.yml` は無変更（Q4）
- U4a で機能化済みの `deploy.yml`（`uv sync → test（unit+PBT）→ d1 migrations apply --remote → deploy`）は、**`migrations apply` が versioned 全 migration を適用**するため、**`0003` はファイル追加のみで自動的に適用対象**に入る（コマンド・ワークフロー変更不要）。deploy.yml 無変更で済むのは U4a で RT-1 を先に消化した配当。
- 静的アセットは `pywrangler deploy` が `[assets]` 設定に従い同時アップロード（§6 検証 ② で確認）。
- Secrets（CI）: 既存 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` のみ（U2 で追加なし）。

### 6-β. Static Assets × Python Workers の beta 検証（Code Generation 冒頭に実施, Q1 補足）
Static Assets × Python Workers は G-1（FastAPI 起動 CPU）と同種の「**本番でしか確信できない**」領域。**Code Generation 冒頭に smoke 流儀の小検証**（最小アセット 1 枚 + `/api/ping` の実機確認）を置き、結果を記録する:
1. **アセット配信と `on_fetch` の実行順**: パスがアセットに一致すればアセット応答、しなければ Worker。**`/api/*` はアセット非一致で Worker に届く**はず — これを実機で確認。
2. **`[assets]` の現行設定キー**（directory / binding 名）と **`pywrangler deploy` でのアセット同時アップロード**の成否。
3. **`run_worker_first` 相当の明示設定の要否**（`/api/*` を Worker 優先にする設定が要るか）。
- **フォールバック（受け皿）**: 順序が想定と異なる → 該当設定で是正。**Static Assets 自体が Python Workers と併用不能な場合のみ** → C（Worker が HTML/JS を `Response` で直接返す埋め込み配信）。**B（Cloudflare Pages 分離）は CORS・二重運用のため最後の手段**。
- **検証対象外**: SPA フォールバック（`not_found_handling`）は不使用のため検証しない（Q2）。

**検証結果（2026-07-14, 初回実デプロイの過程で確定）**:
- **① の確認過程で F-8 を発見・是正**: 初回デプロイ後 `/api/ping` が 1101・tail に `ModuleNotFoundError: No module named 'backend'`。原因＝Python Workers は `main` のディレクトリのみをモジュールルートにバンドルするため、`main="backend/entry.py"` ではルートが `backend/` になり `backend.…`/`schema.…` の絶対 import が解決不能（integration が PASS したのは harness が `src/` 隔離コピーで正しいレイアウトだったから＝本番設定に未伝播）。→ **src/ レイアウトへ移行**（`main="src/entry.py"`・`src/backend/`・`src/schema/`、`pythonpath=["src","."]`、scripts `_bootstrap`、harness cp 元更新）。**F-8 として知見昇格**（§2.1 / shared-infrastructure）。
- **例外がスローされた＝ルーティングは Worker に到達**していたため **beta ① は半分成立済み**。Static Assets 併用不能の C/B フォールバックは**不要**（本件は assets 無関係のバンドル規則の問題）。是正後の残作業は正常応答の確認（`/api/ping` JSON・`/` index.html・`/no-such-path` 404・`/admin/items` 401）のみ＝再デプロイで消化。

## 7. Deployment（Q5）
- U1/U4a の **dev（miniflare/ローカル D1）/ prod（実験用サブドメイン・本番 D1）** 分離を流用。
- **収束**: 参加者フロント・参加者 API・管理 API（U4a）・scripts が **同一 Worker / 同一 D1 / 実験用サブドメイン一本**を共有。トークン配布 URL は当該サブドメイン + `?token=`。

### デプロイ手順（U2・差分）
```
1. frontend/ を配置し wrangler.toml に [assets] を宣言（§2、beta 検証で設定確定）
2. migrations/0003_likert_unique.sql を追加（適用は CI が versioned で自動）
3. CI(deploy.yml, 無変更): uv sync → test → d1 migrations apply --remote(0001+0002+0003) → deploy(アセット同梱)
   ※ U2 で追加シークレットなし
4. 参加者は 実験用サブドメイン/?token=... でアクセス（同一オリジンで /api/* を叩く）
```

## 8. トレーサビリティ
| 項目 | 対応 |
|---|---|
| Static Assets 同一オリジン配信 | Q1 / TSD-U2-01 / LC-U2-08 |
| `/api/*` ルーティング・no-store | Q2 / DP-U2-04 / LC-U2-01 |
| SPA フォールバック不使用 | Q2 補足 |
| CORS なし（同一オリジン） | Q3 / U2-NFR-01 |
| migration 0003・適用順 | Q4 / U2-NFR-15 |
| deploy.yml 無変更（versioned 自動適用） | Q4 / RT-1（U4a 消化の配当） |
| 新規シークレットなし | Secrets 差分なし / U2-NFR-01 |
| beta 3 点検証（Code Generation 冒頭） | Q1 補足 / G-1 と同種 |

## 9. 後続申し送り（Code Generation）
- **冒頭**: 6-β の beta 3 点検証（Static Assets × Python Workers）を smoke 流儀で実施・記録。想定外なら是正 → C → B の順。
- `frontend/` SPA、`wrangler.toml` `[assets]` 設定（検証結果反映）、`migrations/0003_likert_unique.sql`、`schema/` ビュー型 + `likert_fixed_targets`、`backend/participant/`（ParticipantApi + Services + ViewSerializer + ParticipantLog + derive_phase）、`backend/domain/select_likert_targets`、Repository 追加メソッド、PBT（PU2-1/3/6）+ integration（PU2-2/4/5/7/8）。
- README にデプロイ手順（U2 差分）を反映。
