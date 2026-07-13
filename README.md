# nazokake-judge

なぞかけ(謎かけ)の品質を人間評価によって判定するための web アプリケーション。

## 目的

なぞかけの品質を、個人の主観や単発の印象評定ではなく、**ペア比較(A/B 判定)にもとづく統計モデル**で安定して測定する。これにより、制作したなぞかけがプロ作品の水準に対してどこに位置するかを反復的に判定できる「品質判定装置」を構築する。

本アプリは、なぞかけの機知(wit)評価に関する研究プロジェクトの人間評価インフラとして開発される。

## 評価設計の概要

- **判定方式**: 2 作品を並べて提示し、評価者が優劣を選ぶペア比較(A/B 判定)
- **統計モデル**: Bradley–Terry モデルにより全作品を単一の品質尺度上に配置
- **補助指標**: 一部項目に Likert 評定を併用し、BT 尺度上の位置を較正アンカーとして解釈可能にする
- **刺激プール**: 出自の異なる複数の層(プロ作品層 / AI 生成層 / 編集・自作層 / ルールベース生成層)から構成し、品質分布の広がりを確保する
- **セッション構成**: 1 セッションあたり数十ペアの比較 + 少数のブリッジ Likert 項目 + 事後アンケート(所要 25〜35 分程度を想定)

## 想定アーキテクチャ

静的フロントエンド + 軽量バックエンドの構成を想定(最終決定は設計フェーズで行う):

| 構成案 | フロントエンド | バックエンド / DB |
|---|---|---|
| 案 A | 静的 HTML/JS | Cloudflare Workers + D1 |
| 案 B | 静的 HTML/JS | PHP + SQLite (レンタルサーバ) |

いずれの場合も実験用サブドメインに分離してデプロイする。

## 開発プロセス

本プロジェクトは [AI-DLC (AI-Driven Development Life Cycle)](https://github.com/awslabs/aidlc-workflows) のワークフローに沿って開発する。

- **Inception**: 要求定義・ユーザーストーリー・実験プロトコルとの整合確認
- **Construction**: 設計・実装・テスト
- **Operations**: デプロイ・実験運用・データ回収

ルール一式は `aidlc-workflows/`(awslabs のクローン)に配置しており、このリポジトリには含めない(`.gitignore` で除外)。AI-DLC が生成する計画・設計ドキュメントは `aidlc-docs/` 配下に置き、リポジトリで管理する。

## ディレクトリ構成

案 A′（Cloudflare Python Workers + D1）で確定。U1（共有基盤）を実装済み。

```
nazokake-judge/
├── aidlc-docs/          # AI-DLC の計画・設計ドキュメント
├── schema/              # データ契約: Pydantic モデル + トークン契約 + 形式バージョン（U1・全ユニット共有）
├── backend/
│   ├── domain/          # AssignmentEngine（純粋）+ Serializer + pool_sufficiency（U1/U4a）
│   ├── repo/            # D1 Repository（唯一の I/O 境界。書込は U4a で拡張）
│   ├── admin/           # 管理 API（/admin/*）+ Basic 認証 + 秘匿ログ（U4a）
│   ├── log.py           # 構造化ログ（U1）
│   ├── entry.py         # Worker エントリ（on_fetch。/admin/* を配線、参加者ルートは U2）
│   └── participant/     # 参加者フロー（U2, 未生成）
├── frontend/            # 静的 HTML/JS（U2/U3, 未生成）
├── scripts/             # pool_ingest・token_issue（U4a）／bt_aggregate（U4b, 未生成）
├── migrations/          # D1 versioned マイグレーション
├── tests/{unit,pbt}/    # 単体 + プロパティベーステスト（Hypothesis）
├── pyproject.toml       # 依存（Pydantic v2）・ツールチェーン（uv + pywrangler）
├── wrangler.toml        # Workers 設定（python_workers / D1 binding / workers_dev）
└── .github/workflows/   # CI（テスト + デプロイ）
```

> **実装規約（本番 smoke test で確定）**: フレームワークは FastAPI ではなく **raw workers API + Pydantic v2**（起動 CPU 制限のため）。Worker ハンドラは module-level `on_fetch(request, env)`。デプロイは CI（GitHub Actions）経由。

## 注意事項

- なぞかけ刺激データ(作品本文)は権利・匿名性の観点から**このリポジトリには含めない**。刺激はデプロイ時に別経路で投入する。
- 実験参加者の回答データも同様にリポジトリ管理外とする。

## ライセンス

本プロジェクトのコードは [MIT License](LICENSE) の下で公開する。

なお、なぞかけ刺激データおよび実験参加者の回答データはリポジトリに含まれず、MIT の対象外である(「注意事項」参照)。