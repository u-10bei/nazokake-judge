# smoke-test — R-1 / TSD-02 / R-2 先行検証(使い捨て)

U1 Infrastructure Design §2(Q1=A)の smoke test 一式。**5 項目**を最小 Worker で検証し、結果を `infrastructure-design.md` §2 に追記する。検証後このフォルダは削除してよい(結果の記録だけ残す)。

| # | 検証項目 | エンドポイント | 対応 |
|---|---|---|---|
| 1 | `python_workers` flag で Worker 起動 | (応答があること自体) | R-1 |
| 2 | FastAPI (ASGI) ルーティング | `/smoke/fastapi` | R-1 |
| 3 | Pydantic v2 import/validate | `/smoke/pydantic` | TSD-02 |
| 4 | D1 binding 最小クエリ | `/smoke/d1` | R-1/R-2 |
| 5 | D1 batch 原子性 + ON CONFLICT DO NOTHING | `/smoke/d1-batch` | DP-01/DP-02, R-2 |

`GET /smoke/all` が全項目を実行し、`overall_pass` と項目別 PASS/FAIL を JSON で返す。

## 手順(pywrangler / uv ワークフロー)

**重要**: Python Workers のサードパーティ依存(fastapi/pydantic)は **pyproject.toml + pywrangler** で管理する。素の `wrangler dev` や requirements.txt では**ロードされない**(2026-07 検証で確認済みのブロッカー)。

前提: Node.js、**uv**(`curl -LsSf https://astral.sh/uv/install.sh | sh`)、Cloudflare アカウント認証(`npx wrangler login` の OAuth、または `CLOUDFLARE_API_TOKEN` 環境変数)。**認証は自分のマシンで行うこと**(サンドボックス化されたエージェント環境では対話ログイン不可)。

```bash
cd smoke-test

# 1. D1 を作成し、出力の database_id を wrangler.toml に転記
uv run pywrangler d1 create nazokake-smoke

# 2. ローカルで確認(pywrangler が pyproject.toml の依存を自動インストール)
uv run pywrangler d1 migrations apply nazokake-smoke --local
uv run pywrangler dev
#   別ターミナルで:
curl -s http://localhost:8787/smoke/all | python3 -m json.tool

# 3. 本番ランタイムで確認(R-1 の本旨はこちら。ローカル成功だけでは不十分)
uv run pywrangler d1 migrations apply nazokake-smoke --remote
uv run pywrangler deploy
curl -s https://nazokake-smoke.<your-subdomain>.workers.dev/smoke/all | python3 -m json.tool
```

pywrangler は wrangler の全コマンドを受け付ける(`uv run pywrangler --help`)。deploy 時には依存が自動的にバンドルされ、import はデプロイ時にメモリスナップショット化される。

**2(ローカル)と 3(本番)の両方の JSON を記録すること。** miniflare と本番 Pyodide ランタイムは別物なので、R-1 の判定は本番側で行う。

## 結果の解釈と分岐(infrastructure-design.md §2 の判定表)

| 結果 | 分岐 |
|---|---|
| 全項目 PASS | 案 A′ 続行。結果 JSON を infrastructure-design.md §2 に追記して smoke test 完了 |
| 項目 3 のみ FAIL(Pydantic v2 不可) | TSD-02 フォールバック(pydantic v1 pure-python / dataclasses+手書き検証)。DP-07 の狭い公開面により上位無波及 |
| 項目 1/2 FAIL(Workers/FastAPI 自体が不可) | 案 B(PHP+SQLite)へエスカレーション |
| 項目 4/5 FAIL(D1/batch 不可) | R-2 再評価。batch 原子性(5b)のみ FAIL の場合は DP-01 の実現方式を Infrastructure Design に差し戻して再設計 |

## 途中経過(2026-07-12 第1回実行の部分結果)

エージェント環境(認証なし・素の wrangler)での第1回実行により、以下が**確定済み**:

| 項目 | 結果 | 備考 |
|---|---|---|
| 1. python_workers ブート | **実質 PASS** | エラーは `from fastapi import` 行で発生 = Pyodide/Python 自体は起動し標準ライブラリまで実行できている。compatibility_date がランタイムバンドル(Python 3.12/3.13)を選ぶことも確認 |
| DDL 適用(R-2 スキーマ面) | **PASS** | UNIQUE(token,pair_id)・NOT NULL を含む migrations がローカル D1 にクリーン適用 |
| 2/3/4/5 実行時検証 | **未了** | ブロッカー = 依存ロード方式(→ pywrangler で解消)+ Cloudflare 認証(→ 自分のマシンで実行) |

残る検証は項目 2(FastAPI)/3(Pydantic v2)/4(D1 binding)/5(batch)の実行時動作。上記手順を**認証済みの自分のマシン**で実行し、ローカル・本番両方の `/smoke/all` JSON を記録する。

## 実装メモ(ハマりそうな点)

- **env の取得**: FastAPI ルート内では `request.scope["env"]` で取得(取れない場合は `from workers import env` にフォールバックする実装にしてある)。
- **JsProxy**: D1 の返り値は JS オブジェクトのことがあるため `_to_py()` で変換している。
- **batch の引数**: JS 配列を期待するため `pyodide.ffi.to_js` で変換(`_to_js_maybe`)。
- **beta 由来の API ドリフト**: Python Workers は open beta のため、上記の呼び出し形が現行ランタイムとずれている可能性がある。エラーが出たら、それ自体が R-1 の検証結果なのでエラーメッセージごと記録して持ち帰ること(コードを直して再試行してよいが、どう直したかも記録)。
- **compatibility_date**: wrangler が日付でエラーを出す場合は手元の wrangler が示す最新サポート日付に下げてよい。
- **後片付け**: 検証完了後、`npx wrangler delete nazokake-smoke`(Worker)と `npx wrangler d1 delete nazokake-smoke`(DB)で削除可。
