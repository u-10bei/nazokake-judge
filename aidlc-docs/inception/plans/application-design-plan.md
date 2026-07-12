# Application Design Plan — nazokake-judge

**役割**: ソフトウェアアーキテクト
**目的**: 要件・ストーリーを、高レベルのコンポーネント構成 / サービス境界 / 依存関係の設計へ落とす。
**スコープ注記**: ここでは**高レベル設計**（コンポーネント識別・インターフェース・サービス層）を決める。詳細な業務ロジックは Construction フェーズの Functional Design（per-unit）で扱う。

このドキュメントは **Planning** 成果物です。下部の質問（`[Answer]:`）にすべて回答いただいた後、承認を得てから設計成果物（components.md 他）を生成します。

---

## 生成予定の設計成果物（承認後に作成）

- [x] `application-design/components.md`（コンポーネント定義・責務・インターフェース）
- [x] `application-design/component-methods.md`（メソッド署名・入出力型。業務ルール詳細は Functional Design）
- [x] `application-design/services.md`（サービス定義・オーケストレーション）
- [x] `application-design/component-dependency.md`（依存マトリクス・通信パターン・データフロー）
- [x] `application-design/application-design.md`（上記を統合した設計書）
- [x] 設計の完全性・整合性の検証（要件/ストーリー/XC 制約とのトレース）

**Part 1 回答サマリ**: Q1=X(案 A′: Python Workers+D1, Hypothesis) / Q2=A(バニラ JS) / Q3=A(セッション開始時一括生成→DB 保存) / Q4=A(サーバ DB 単一の真実) / Q5=B(Basic 認証) / Q6=A(schema/ 単一仕様+Pydantic 共有)

---

## 参考: アーキテクチャ案 A/B のトレードオフ（Q1 用）

| 観点 | 案 A: 静的フロント + Cloudflare Workers + D1 | 案 B: 静的フロント + PHP + SQLite（レンタルサーバ） |
|---|---|---|
| 実行モデル | サーバレス（エッジ関数） | 従来型（レンタルサーバ上の PHP） |
| DB | D1（SQLite 互換、マネージド） | SQLite（ファイル） |
| スケール | 自動（小規模には過剰なほど） | 手動（ただし小規模なら十分） |
| HTTPS | 標準で付与 | サーバ設定に依存（要確認） |
| 割当ロジック実装言語 | TypeScript / JavaScript | PHP |
| PBT エコシステム | fast-check（TS、成熟） | Eris 等（PHP、相対的に弱め） |
| デプロイ | wrangler / CI | ファイル配置（FTP 等）で単純 |
| ローカル開発 | wrangler（Miniflare） | PHP + SQLite（容易） |
| 同時実行 | エッジで自然にさばける | SQLite の書込ロックに留意（小規模なら可） |
| コスト | 無料枠で収まる見込み | 既存レンタルサーバ契約を流用 |

> 規模は小（数十名・同時数名）のため**どちらでも機能的には充足**。差が出るのは主に「割当ロジックの PBT エコシステム（案 A 有利）」と「デプロイ/運用の慣れ・既存資産（案 B が既存契約流用で単純）」。両案とも運用基盤（ドメイン・契約）は確保済み。

---

## 質問（すべて回答してください）

回答方法: 各質問の選択肢から 1 つ選び、`[Answer]:` の後ろに**記号**を記入してください。該当がなければ「Other」を選び自由記述してください。記入後「done」等でお知らせください。

## Question 1
採用するアーキテクチャ案は?（最重要・requirements §6 の申し送り）

A) 案 A: 静的フロント + Cloudflare Workers + D1

B) 案 B: 静的フロント + PHP + SQLite（レンタルサーバ）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
フロントエンドの実装形態は?（モバイルファースト・日本語のみ・静的配信）

A) バニラ JS + 最小限の CSS（ビルド不要、依存最小）

B) 軽量ライブラリ（Alpine.js 等）で状態管理を補助

C) SPA フレームワーク（React / Svelte 等、ビルドあり）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
ペア割当（XC-01 の純粋関数）を「いつ・どこで」実行し、何を権威とするか?

A) セッション開始時にバックエンドで、現在の露出カウントを読んでそのセッション分のペア列を確定し DB 保存（以後はそれに従う）

B) ペア提示ごとにバックエンドで逐次生成（毎回、最新の露出カウントを参照）

C) 事前に全参加者分のペア列をバッチ生成して DB 格納（参加者数が確定してから）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
セッション状態（回答済みペア・進捗・再開位置）の権威的な保持先は?

A) サーバ DB を単一の真実とする（クライアントは表示のみ、再開はサーバ状態から復元）

B) サーバ DB を権威としつつ、クライアントにも一時状態を持たせオフライン耐性を上げる

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5
管理画面（US-R01 進捗 / US-R03 暫定勝率）とエクスポート（US-R02）の保護方式は?

A) 管理用シークレット（管理トークン/パスワード）による単純な保護

B) Basic 認証（サーバ/エッジの機能を利用）

C) 管理機能は公開せず、進捗・エクスポートも `scripts/` 経由（DB 直参照）に寄せる

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
アプリ本体と集計/運用スクリプト（Python）間の「データ契約」の共有方法は?（US-R02↔US-R04 整合、US-R06 層ラベル）

A) DB スキーマとエクスポート形式を単一の仕様書（`schema/`）で定義し、両者がそれを参照

B) エクスポートの CSV/JSON 形式のみを固定仕様とし、DB 内部は各実装に委ねる

C) スクリプトはアプリと同じ DB ファイル/接続を直接読む（案 B 採用時に特に有効）

X) Other (please describe after [Answer]: tag below)

[Answer]: 
