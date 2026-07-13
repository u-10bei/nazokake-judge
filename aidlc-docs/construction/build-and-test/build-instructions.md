# Build Instructions — nazokake-judge（U1 共有基盤）

## Prerequisites
- **ツールチェーン**: uv（0.10+）+ pywrangler（`workers-py`）。Node.js 22（pywrangler が npx wrangler を呼ぶ）。
- **依存**: `pyproject.toml` の `dependencies`（Pydantic v2）+ dev グループ（workers-py / workers-runtime-sdk / hypothesis / pytest）。**`requirements.txt` は不可**（F-1）。
- **環境変数**: デプロイ時のみ `CLOUDFLARE_API_TOKEN`（Workers Scripts:Edit + D1:Edit）/ `CLOUDFLARE_ACCOUNT_ID`。ローカルは不要。
- **システム**: Linux/CI（**Windows ネイティブの pywrangler は非サポート**, F-3。WSL で回避可）。

## Build Steps

### 1. 依存導入
```bash
uv sync                      # または uv run --group dev <cmd> で都度解決
```

### 2. Worker のバンドル確認（デプロイなし）
Python Workers は「ビルド」= バンドル。`pywrangler dev`/`deploy` 時に `pyproject.toml` の依存が
自動ベンダリングされる。`main = backend/entry.py`（module-level `on_fetch`, raw workers API）。

### 3. デプロイ（CI 経由, F-3）
```bash
# .github/workflows/deploy.yml が実行:
uv run --group dev pytest -q          # テスト（下記）
uv run pywrangler d1 migrations apply nazokake-judge --remote
uv run pywrangler deploy
```
`wrangler.toml` の `database_id` を実 D1 に設定すること。

## Build Artifacts
- Worker バンドル（CI/デプロイ時に生成、リポジトリには置かない）。
- D1 スキーマ: `migrations/0001_init.sql`。

## Troubleshooting
- **`ModuleNotFoundError`（fastapi 等）** → 依存を `pyproject.toml` に宣言。`requirements.txt` は削除（F-1）。
- **起動 CPU 制限 10021** → 重いトップレベル import を避ける。FastAPI は採用不可（raw workers API, F-4）。
- **`Method on_fetch does not exist`** → ハンドラは module-level `async def on_fetch(request, env)`（F-5）。
- **バンドルが巨大化/ハング** → `main` をソース隔離ディレクトリに置き `node_modules`/`.venv` を巻き込ませない（F-6）。
