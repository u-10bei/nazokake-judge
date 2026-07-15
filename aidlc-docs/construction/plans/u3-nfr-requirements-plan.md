# U3 NFR Requirements Plan — 研究者・管理（admin）

**ユニット**: U3（C-FE-ADMIN / C-SVC-ADMIN / C-SVC-EXPORT / C-AUTH〈再利用〉/ C-API〈管理系〉）
**目的**: U3 の非機能要件を確定する。U3 は **既存 Basic 認証境界の再利用・読み取り専用**のため差分は小さいが、**エクスポート（トークン付き研究データ）の秘匿・取扱**が固有論点。集計・エクスポートの正しさ（練習除外・契約整合）は Functional Design（BR-U3-03/07）で決定済みなので NFR として明文化する。
**前提（既決）**: 拡張 opt-in は U1〜U2 と共通（Security Baseline=No / Resiliency=No / **PBT=Partial**、強制 PBT-02/03/07/08/09）。案 A′（Python Workers + D1, raw workers API + Pydantic v2, **src/ レイアウト F-8**）。監視基盤なし（stdout JSON）。管理境界（Basic 認証・`ADMIN_BASIC_*`）は U4a 導入済み・U3 が再利用。

このドキュメントは **Part 1（Plan + 質問）**。回答・承認後に `nfr-requirements.md`（U3-NFR-NN）/ `tech-stack-decisions.md`（U3 追加分）を生成します。

## 生成予定の成果物（Part 2）→ 生成済み（2026-07-15）
- [x] `construction/u3/nfr-requirements/nfr-requirements.md`（U3-NFR-01〜: エクスポート秘匿・認証再利用/CORS なし・SLO なし・テスト振り分け・非BT 明示 + 非目標）
- [x] `construction/u3/nfr-requirements/tech-stack-decisions.md`（TSD-U3-01〜: 認証再利用・管理 HTML の src/ 埋め込み・集計 SQL の Repository 集約・CSV 直列化・テスト）

**回答サマリ**: 全 5 問 ★A。Data/Migration・Scalability/Resiliency=N/A（読み取り専用）に同意。Q4 で PBT は PU3-3 のみ候補・他は非該当明記。

---

## NFR カテゴリ適用性（U3）
| カテゴリ | 適用 | 備考 |
|---|---|---|
| **Security** | **適用（最重要）** | 管理 UI/API/エクスポートの Basic 認証一本化・管理 HTML の assets 非配置・エクスポート秘匿（トークン付きデータの取扱）。→ Q1/Q2 |
| **Performance** | 適用（最小限） | 集計クエリ（進捗/勝率/エクスポート join）の SLO 姿勢。→ Q3 |
| **Testability** | 適用 | PU3-1〜5 の PBT/integration 振り分け。→ Q4 |
| **Usability** | 適用（限定） | 管理 UI はデスクトップ主・非BT 明示（BR-U3-05/10）。XC-04 逸脱は FD で記録済み。→ Q5 |
| **Reliability** | 適用（軽微） | 読み取り専用（書き込み・冪等・原子性は対象外）。整合は集計の正しさ（Testability）で担保。 |
| **Observability** | 最小限（流用） | AdminLog 再利用（トークン・本文非出力）。 |
| **Data/Migration** | **N/A** | **U3 は読み取り専用＝新規テーブル・DDL 変更なし（migration なし）**。 |
| **Scalability/Resiliency** | N/A | 単独研究者・小規模。 |

---

## 質問（回答は各 `[Answer]:` に記入。特記なき場合 **★A=推奨デフォルト**）

### Q1【Security】エクスポートデータ（トークン付き研究データ）の秘匿・取扱
エクスポートは**トークン単位で紐付く回答データ**（評価者相対性分析用, US-R02）を Basic 認証背後で返す。
- **★A（推奨）**: (i) エクスポートは **Basic 認証必須・HTTPS 強制**（`/admin/*` 一本, BR-U3-01）。(ii) エクスポート**応答自体はトークンを含む**（研究者が必要・認証背後）が、**ログには出さない**（AdminLog 秘匿, BR-U3-08）。(iii) エクスポート応答に **`Cache-Control: no-store`**（トークン付きデータのキャッシュ滞留防止）。(iv) **本文（body）はエクスポートに含めない**（未公表刺激, BR-U3-07/NFR-08）。(v) エクスポートファイルの保管（研究者のローカル）は運用責任＝リポジトリ管理外（NFR-08）。
- **B**: エクスポートのトークンを仮名化（ハッシュ）して返す。→ 評価者相対性分析（同一評価者の回答束ね）に実トークンが要るため、認証背後で実トークンを返す A が適切。仮名化は U4b/分析側の選択に委ねる。

[Answer]: A — Basic 認証必須 + HTTPS / 応答は実トークンを含む（ログには出さない）/ no-store / body 非含有 / ローカル保管は運用責任。補足: B（仮名化）却下＝評価者相対性分析には同一評価者の回答を束ねる実トークンが必要。仮名化の要否は分析・公表側（U4b/論文執筆時）の選択に委ねるのが正しい責務配置。

### Q2【Security】管理境界の露出・CORS・認証情報
- **★A（推奨）**: 管理 UI/API は **U4a と同一の Basic 認証境界（単一資格 `ADMIN_BASIC_*`）を再利用**（新規資格・新規認証を作らない）。**管理 HTML は `src/` 埋め込みで Worker が返す**（Static Assets に置かない, BR-U3-02）。**CORS は設けない**（同一オリジン・ブラウザから同一サブドメインの `/admin/*` を叩く。U4a-NFR-02 と同方針、管理 UI もブラウザだが同一オリジンゆえ不要）。定数時間比較（既存 AuthGuard 流用）。
- **B**: U3 用に別資格・別境界。→ 鍵管理二重化・境界の作り直し。不採用。

[Answer]: A — U4a と同一の Basic 認証境界（単一資格）を再利用。管理 HTML は src/ 埋め込み（BR-U3-02）。CORS なし（同一オリジン）。補足: 「管理 UI もブラウザ利用だが同一オリジンゆえ CORS 不要」の明示で、U2 NFR 時点で予告した「U3 での CORS 拡張検討」は不要と正式決着。

### Q3【Performance】集計クエリの SLO 姿勢
進捗カウント・勝率集計・エクスポート join は全 D1 スキャンだが小規模（〜50 セッション × 約 43 ペア ≈ 2,000 判定行 + items 95）。
- **★A（推奨）**: **明示的な数値 SLO は設定しない**（U1/U2 と同方針）。参考目安「進捗/勝率 < 1s・エクスポート < 数秒」。想定規模では単一集計クエリで実質瞬時。インデックス追加・マテリアライズ・ページングは**不要**。
- **B**: 数値 SLO とインデックス最適化を要件化。→ 小規模に過剰。

[Answer]: A — 数値 SLO なし。参考目安「進捗/勝率 < 1s・エクスポート < 数秒」。インデックス追加・マテリアライズ・ページング不要。補足: 想定規模（判定 ≈ 2,000 行 + items 95）で単一集計クエリは実質瞬時。U1/U2 と同判断の三度目の一貫適用。

### Q4【Testability】PU3-1〜5 の PBT/統合の振り分け
- **★A（推奨）**: **純粋な整形ロジックは example ベース単体テスト**、**D1 集計は統合テスト**（`tests/integration/` 流用・`/admin/*` 越し）に振り分け:
  - unit（純粋）: CSV 直列化・ProgressView/WinrateRow 変換・ExportBundle 組立（形式・自己完結性の構造検証 PU3-3）。
  - integration（実 D1）: PU3-1（練習除外の出力段保証）・PU3-2（winrate 定義整合）・PU3-4（進捗カウント整合）・PU3-5（認証 401）。
  - PBT 強制セット（PBT-02/03/07/08/09）は U3 では該当薄（新規純粋不変条件が乏しい）。**ExportBundle 自己完結（judgments の item ⊆ items）は PBT 候補**（生成データで検証）。非該当は明記。
- **B**: すべて統合テスト。→ 整形ロジックの反例探索が弱くなる。

[Answer]: A — 純粋整形は example ベース単体 / D1 集計・認証は統合（/admin/* 越し）。PBT 強制セットは U3 で該当薄と**非該当明記**、PU3-3（ExportBundle 自己完結: judgments の item ⊆ items）のみ PBT 候補。補足: 非該当明記は拡張適合（Requirements Q14 Partial）の監査に必要。PU3-3 は包含関係の反例探索が Hypothesis に適する。

### Q5【Usability】管理 UI の可用性水準
- **★A（推奨）**: **デスクトップ主・日本語**（研究者 P-RSCH）。**非 BT の明示**（暫定勝率に常時注記, BR-U3-05）を可用性要件として固定。アクセシビリティは合理的水準（セマンティック HTML・キーボード操作可）、正式 WCAG 準拠は非目標。モバイルは破綻しない程度（厳密最適化は非目標＝XC-04 逸脱を FD で記録済み, BR-U3-10）。
- **B**: 管理 UI もモバイルファースト厳守。→ 研究者利用実態（PC）に対し過剰。

[Answer]: A — デスクトップ主・日本語・**非 BT の明示を可用性要件として固定**・合理的アクセシビリティ・モバイルは破綻しない程度。補足: 「非 BT 明示」の要件昇格は妥当＝暫定勝率が正式 BT 推定と誤読される事故は反復判定装置運用の現実的な認知リスク。

---

**回答後の流れ**: 曖昧点を点検（あれば追加質問）→ Part 2 で `nfr-requirements.md`（U3-NFR-NN）/ `tech-stack-decisions.md`（U3 追加分）を生成 → 標準 2 択（Request Changes / Continue → **NFR Design〈U3〉**）。回答は本 plan の各 `[Answer]:` 欄へ書き戻す。
