"""AdminUI（LC-U3-06）— 管理ダッシュボードの埋め込み HTML/JS/CSS（モジュール定数）。

**Static Assets に置かない**（公開漏れ防止, BR-U3-02）。`handle_admin` が `GET /admin/` で
本定数を `text/html` として返す（Basic 認証背後）。デスクトップ主・日本語（BR-U3-10）。
ブラウザは `/admin/` で一度 Basic 認証し、以降の fetch も同資格。
"""

from __future__ import annotations

ADMIN_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>なぞかけ品質評価 — 研究者管理</title>
<style>
  body { font-family: system-ui, "Noto Sans JP", sans-serif; margin: 0; background:#f7f7f8; color:#1b1b1f; }
  header { background:#2f3a56; color:#fff; padding:14px 20px; }
  h1 { font-size:1.2rem; margin:0; }
  main { max-width:1000px; margin:0 auto; padding:20px; }
  section { background:#fff; border:1px solid #d9d9e0; border-radius:10px; padding:16px; margin-bottom:20px; }
  h2 { font-size:1.05rem; margin:.2em 0 .6em; }
  .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
  .stat { background:#f0f2f8; border-radius:8px; padding:12px; text-align:center; }
  .stat b { display:block; font-size:1.6rem; }
  .stat span { font-size:.85rem; color:#5c5c66; }
  table { width:100%; border-collapse:collapse; font-size:.9rem; }
  th, td { border-bottom:1px solid #e5e5ea; padding:8px 10px; text-align:right; }
  th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) { text-align:left; }
  thead th { background:#f0f2f8; cursor:pointer; user-select:none; }
  .note { background:#fff4d6; border:1px solid #e8cf7a; border-radius:8px; padding:8px 12px; font-size:.85rem; margin-bottom:10px; }
  button, a.btn { font:inherit; cursor:pointer; border:1px solid #2f57d6; background:#2f57d6; color:#fff;
    border-radius:8px; padding:10px 14px; text-decoration:none; display:inline-block; margin:4px 6px 4px 0; }
  a.btn.sec { background:#fff; color:#2f57d6; }
  .muted { color:#5c5c66; font-size:.85rem; }
</style>
</head>
<body>
<header><h1>なぞかけ品質評価 — 研究者管理</h1></header>
<main>
  <section data-testid="progress-panel">
    <h2>進捗</h2>
    <div class="grid" id="progress">
      <div class="stat"><b id="p-issued">–</b><span>トークン発行</span></div>
      <div class="stat"><b id="p-started">–</b><span>開始</span></div>
      <div class="stat"><b id="p-completed">–</b><span>完了</span></div>
      <div class="stat"><b id="p-judgments">–</b><span>本番判定</span></div>
      <div class="stat"><b id="p-likert">–</b><span>Likert 回答</span></div>
      <div class="stat"><b id="p-survey">–</b><span>アンケート</span></div>
    </div>
    <button id="refresh" data-testid="admin-refresh-button">更新</button>
  </section>

  <section data-testid="winrate-panel">
    <h2>暫定勝率</h2>
    <div class="note">これは<strong>簡易表示</strong>であり、正式な BT（Bradley–Terry）推定ではありません。傾向確認用です。</div>
    <table data-testid="winrate-table">
      <thead><tr>
        <th data-k="item_id">item_id</th><th data-k="layer">layer</th>
        <th data-k="matches">対戦数</th><th data-k="wins">勝ち</th><th data-k="winrate">勝率</th>
      </tr></thead>
      <tbody id="winrate-body"></tbody>
    </table>
  </section>

  <section data-testid="export-panel">
    <h2>エクスポート</h2>
    <p class="muted">JSON は BT 集計（U4b）の入力の正本です。CSV は目視用途（エンティティ別）。</p>
    <a class="btn" href="/admin/export?format=json" data-testid="admin-export-json-button">JSON をダウンロード</a>
    <div>
      <a class="btn sec" href="/admin/export?format=csv&entity=judgments" data-testid="admin-export-csv-judgments-button">CSV: judgments</a>
      <a class="btn sec" href="/admin/export?format=csv&entity=likert" data-testid="admin-export-csv-likert-button">CSV: likert</a>
      <a class="btn sec" href="/admin/export?format=csv&entity=surveys" data-testid="admin-export-csv-surveys-button">CSV: surveys</a>
      <a class="btn sec" href="/admin/export?format=csv&entity=items" data-testid="admin-export-csv-items-button">CSV: items</a>
    </div>
  </section>
</main>
<script>
async function load() {
  const p = await (await fetch('/admin/progress', {cache:'no-store'})).json();
  document.getElementById('p-issued').textContent = p.tokens_issued;
  document.getElementById('p-started').textContent = p.tokens_started;
  document.getElementById('p-completed').textContent = p.tokens_completed;
  document.getElementById('p-judgments').textContent = p.judgments_total;
  document.getElementById('p-likert').textContent = p.likert_total;
  document.getElementById('p-survey').textContent = p.survey_total;

  const rows = await (await fetch('/admin/winrates', {cache:'no-store'})).json();
  renderWinrates(rows);
}
let _rows = [];
function renderWinrates(rows) {
  _rows = rows;
  const tb = document.getElementById('winrate-body');
  tb.innerHTML = rows.map(r =>
    `<tr><td>${esc(r.item_id)}</td><td>${esc(r.layer)}</td><td>${r.matches}</td>`+
    `<td>${r.wins}</td><td>${(r.winrate*100).toFixed(1)}%</td></tr>`).join('');
}
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
document.querySelectorAll('thead th').forEach(th => th.onclick = () => {
  const k = th.dataset.k;
  _rows.sort((a,b)=> (b[k]>a[k]?1:b[k]<a[k]?-1:0));
  renderWinrates(_rows);
});
document.getElementById('refresh').onclick = load;
load();
</script>
</body>
</html>
"""
