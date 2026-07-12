# 要求明確化のための質問 (Requirements Verification Questions)

プロジェクト: **nazokake-judge**（なぞかけ品質判定 Web アプリ）

README に記載済みの内容（ペア比較 / Bradley–Terry モデル / 多層刺激プール / 1 セッション数十ペア + ブリッジ Likert + 事後アンケート / 所要 25〜35 分 / 実験用サブドメインに分離デプロイ）は**確定インプット**として扱います。以下は、まだ曖昧または未決定の点についての確認です。

回答方法: 各質問の選択肢（A, B, C, ...）から 1 つ選び、`[Answer]:` の後ろに**記号**を記入してください。どれも当てはまらない場合は最後の「Other」を選び、`[Answer]:` の後ろに自由記述してください。すべて記入したら「done」等でお知らせください。

---

## Question 1
評価者（実験参加者）はどのようにアプリへアクセスしますか（認証方式）?

A) 匿名リンクのみ（URL を知っていれば誰でも参加可、アカウント登録なし）

B) 共通パスコード / 招待コード（配布したコード入力で参加、個人特定なし）

C) 参加者ごとに発行する個別トークン付き URL（参加者を区別して回答を紐付け）

D) メールアドレス等によるログイン / アカウント登録

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 2
比較ペアの選び方はどうしますか?

A) 事前に固定した設計（全参加者に同一または計画的に割り当てたペア列）

B) ランダム抽出（プールからその場でランダムにペアを生成）

C) 適応的サンプリング（これまでの結果をもとに情報量の多いペアを動的に選ぶ / アクティブラーニング）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 3
想定する評価者の規模はどの程度ですか（性能・スケール要件の目安）?

A) 小規模（総参加者 〜数十名、同時アクセスはごく少数）

B) 中規模（総参加者 数百名、同時アクセス 十数名程度）

C) 大規模（総参加者 千名以上、同時アクセスが多くスケール設計が必要）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 4
対応デバイス / 画面はどこまで想定しますか?

A) PC（デスクトップ）ブラウザのみ

B) スマートフォン / タブレットのみ

C) PC・スマホ両対応（レスポンシブ）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 5
UI の対応言語は?

A) 日本語のみ

B) 日本語 + 英語（多言語切替）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 6
セッション途中での中断・再開をサポートしますか?

A) サポートする（途中保存し、後で続きから再開できる）

B) サポートしない（1 回で最後まで実施、離脱した回答は破棄または部分保存のみ）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 7
BT 尺度（品質ランキング）の集計はどの形で行いますか?

A) オフラインのバッチ集計スクリプト（DB からデータを吐き出し、別途 Python 等で BT 推定）

B) 管理画面上でのオンライン集計・可視化（アプリ内で結果を確認できる）

C) 両方（回収はアプリ、確認用の簡易表示 + 本格集計はオフライン）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 8
管理者（研究者）向け機能はどこまで必要ですか?

A) データエクスポート（CSV/JSON ダウンロード）のみ

B) エクスポート + 進捗モニタリング（参加者数・回答数の確認）

C) エクスポート + 進捗 + 刺激プールの管理 UI（作品の追加・編集）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 9
事後アンケートで収集する情報の範囲は?（複数該当する場合は Other に列挙可）

A) 最小限（なぞかけ経験の有無 / 自己申告の熟達度 程度）

B) 標準（上記 + 年代・性別などの基本デモグラフィック）

C) 詳細（上記 + 判定時に重視した観点などの評価態度に関する設問）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 10
刺激プールの規模感（初期投入する作品数）の想定は?

A) 小（〜50 作品程度）

B) 中（50〜200 作品程度）

C) 大（200 作品以上）

D) 未定（設計・実験計画側で後日確定）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 11
アーキテクチャの方向性について、現時点の選好は?（README の案 A / 案 B）

A) 案 A: 静的フロント + Cloudflare Workers + D1 を優先検討

B) 案 B: 静的フロント + PHP + SQLite（レンタルサーバ）を優先検討

C) 設計フェーズ（Application Design）で比較検討して決定（現時点では決めない）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

---

## 拡張機能の適用可否（AI-DLC Extensions）

以下は AI-DLC のオプション拡張ルールです。プロジェクトに適用するかを選んでください。

## Question 12: Security Extensions
セキュリティ拡張ルールをこのプロジェクトに適用（ブロッキング制約として強制）しますか?

A) Yes — すべての SECURITY ルールをブロッキング制約として強制する（本番運用グレードのアプリに推奨）

B) No — SECURITY ルールをスキップする（PoC・プロトタイプ・実験的プロジェクト向け）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 13: Resiliency Extensions
レジリエンシー（回復性）ベースラインを適用しますか?（AWS Well-Architected 信頼性の柱に基づく設計時ベストプラクティス。本番認証ではなく「第一草案」としての指針）

A) Yes — レジリエンシーベースラインを設計時の指針として適用する（ビジネスクリティカルなワークロードに推奨）

B) No — レジリエンシーベースラインをスキップする（PoC・プロトタイプ・迅速な反復を優先する実験的プロジェクト向け）

X) Other (please describe after [Answer]: tag below)

[Answer]: 

## Question 14: Property-Based Testing Extension
プロパティベーステスト（PBT）ルールを適用しますか?

A) Yes — すべての PBT ルールをブロッキング制約として強制する（業務ロジック・データ変換・シリアライズ・状態を持つコンポーネントがあるプロジェクトに推奨）

B) Partial — 純粋関数とシリアライズのラウンドトリップに限って PBT ルールを強制する（アルゴリズム的複雑さが限定的なプロジェクト向け）

C) No — すべての PBT ルールをスキップする（単純な CRUD・UI のみ・薄い連携層など、重要な業務ロジックがないプロジェクト向け）

X) Other (please describe after [Answer]: tag below)

[Answer]: 
