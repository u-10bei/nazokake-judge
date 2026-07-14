/* U2 参加者ウィザード（バニラ JS SPA）。
 *
 * サーバ権威（U2-NFR-09）: 画面はサーバの SessionView.phase に従って描画し、
 * クライアントは楽観更新しない。状態は localStorage にトークンのみ保持（Infra/Q10）。
 * 送信失敗はサーバ冪等（BR-U2-11/17）を前提に軽くリトライする。
 */
"use strict";

const $ = (sel) => document.querySelector(sel);
const screen = () => $("#screen");

// ---- トークン解決（URL ?token= を localStorage に保存, U2-NFR-04）----
function resolveToken() {
  const u = new URL(window.location.href);
  const q = u.searchParams.get("token");
  if (q) {
    localStorage.setItem("nazokake_token", q);
    return q;
  }
  return localStorage.getItem("nazokake_token");
}
const TOKEN = resolveToken();

// ---- API 呼び出し（no-store・軽いリトライ）----
async function api(path, { method = "GET", body = null } = {}) {
  let lastErr;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const res = await fetch(path, {
        method,
        headers: body ? { "content-type": "application/json" } : {},
        body: body ? JSON.stringify(body) : null,
        cache: "no-store",
      });
      return await res.json();
    } catch (e) {
      lastErr = e;
      await new Promise((r) => setTimeout(r, 300 * (attempt + 1))); // バックオフ
    }
  }
  throw lastErr;
}

function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  t.className = "toast" + (isErr ? " err" : "");
  setTimeout(() => { t.hidden = true; }, 2500);
}

// ---- エントリ ----
async function boot() {
  if (!TOKEN) return renderError("URL にトークンがありません。配布された URL からアクセスしてください。");
  try {
    const view = await api(`/api/session?token=${encodeURIComponent(TOKEN)}`);
    render(view);
  } catch (e) {
    renderError("通信に失敗しました。時間をおいて再度アクセスしてください。");
  }
}

// ---- ルーティング（サーバ権威）----
function render(view) {
  if (view && view.ok === false) return renderError(view.error || "エラーが発生しました。");
  if (!view || !view.phase) return renderError("不正な応答です。");

  if (view.status === "completed" || view.phase === "done") return renderDone();
  switch (view.phase) {
    case "practice":
      // 練習判定 0 件なら教示を前置（UI 規約 BR-U2-02）。
      if (view.practice && view.practice.done === 0) return renderInstruction(view);
      return renderPair(view, true);
    case "judging":
      return renderPair(view, false);
    case "likert":
      return renderLikert(view);
    case "survey":
      return renderSurvey(view);
    default:
      return renderError("未知のフェーズです。");
  }
}

// ---- 画面: 教示 ----
function renderInstruction(view) {
  screen().innerHTML = `
    <h1>なぞかけ品質評価</h1>
    <p>2 つの作品（A・B）を読み比べ、より優れていると感じた方を選んでください。</p>
    <p class="muted">まず数問の<strong>練習</strong>を行います。練習は集計には含まれません
      （優劣に唯一の正解はありません。操作に慣れることが目的です）。</p>
    <button class="primary" id="start" data-testid="instruction-start-button">練習をはじめる</button>
  `;
  $("#start").onclick = () => renderPair(view, true);
}

// ---- 画面: ペア判定（練習/本番共通）----
function renderPair(view, isPractice) {
  const pair = view.next_pair;
  if (!pair) { // 念のため：次が無ければ再取得
    return refresh();
  }
  const prog = view.progress || { done: 0, total: 0 };
  const pr = view.practice || { done: 0, total: 0 };
  const pct = prog.total ? Math.round((prog.done / prog.total) * 100) : 0;

  screen().innerHTML = `
    ${isPractice ? `<div class="practice-banner" data-testid="practice-banner">練習中（この回答は集計されません）　${pr.done + 1} / ${pr.total}</div>`
      : `<div class="progress" data-testid="judging-progress">本番 ${prog.done} / ${prog.total}
           <div class="progress-bar"><span style="width:${pct}%"></span></div></div>`}
    <h2>どちらが優れていますか？</h2>
    <div class="choice-row">
      <button class="item-card choice" data-choice="A" data-testid="judging-choice-a-button">
        <span class="item-label">A</span>
        <div class="item-body">${escapeHtml(pair.left.body)}</div>
      </button>
      <button class="item-card choice" data-choice="B" data-testid="judging-choice-b-button">
        <span class="item-label">B</span>
        <div class="item-body">${escapeHtml(pair.right.body)}</div>
      </button>
    </div>
    <button class="primary" id="submit" disabled data-testid="judging-submit-button">送信</button>
  `;

  let choice = null;
  screen().querySelectorAll(".choice").forEach((btn) => {
    btn.onclick = () => {
      choice = btn.dataset.choice;
      screen().querySelectorAll(".choice").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      $("#submit").disabled = false;    // 選択前は送信不可（BR-U2-12）
    };
  });

  $("#submit").onclick = async () => {
    if (!choice) return;
    $("#submit").disabled = true;
    try {
      const result = await api("/api/judgment", {
        method: "POST",
        body: { token: TOKEN, pair_id: pair.pair_id, choice },
      });
      if (result.ok === false) { toast(result.error, true); return refresh(); }
      // 同フェーズで次ペアがあれば直接描画、フェーズが進んだら全体を再取得。
      if ((result.phase === "practice" || result.phase === "judging") && result.next_pair) {
        render({ ...view, phase: result.phase, next_pair: result.next_pair,
                 progress: result.progress,
                 practice: incPractice(view, result.phase) });
      } else {
        refresh();
      }
    } catch (e) {
      toast("送信に失敗しました。もう一度お試しください。", true);
      $("#submit").disabled = false;
    }
  };
}

function incPractice(view, phase) {
  if (phase !== "practice") return view.practice;
  const pr = view.practice || { done: 0, total: 0 };
  return { done: pr.done + 1, total: pr.total };
}

// ---- 画面: Likert ----
function renderLikert(view) {
  const target = view.next_likert;
  if (!target) return refresh();
  const scale = target.scale || { min: 1, max: 7 };
  let buttons = "";
  for (let n = scale.min; n <= scale.max; n++) {
    buttons += `<button class="likert-btn" data-val="${n}" data-testid="likert-scale-${n}-button">${n}</button>`;
  }
  screen().innerHTML = `
    <h2>この作品の出来を評価してください</h2>
    <div class="item-card"><div class="item-body">${escapeHtml(target.body)}</div></div>
    <p class="muted">${scale.min}（低い）〜 ${scale.max}（高い）</p>
    <div class="likert-scale">${buttons}</div>
    <button class="primary" id="submit" disabled data-testid="likert-submit-button">送信</button>
  `;
  let rating = null;
  screen().querySelectorAll(".likert-btn").forEach((btn) => {
    btn.onclick = () => {
      rating = parseInt(btn.dataset.val, 10);
      screen().querySelectorAll(".likert-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      $("#submit").disabled = false;
    };
  });
  $("#submit").onclick = async () => {
    if (rating == null) return;
    $("#submit").disabled = true;
    try {
      const v = await api("/api/likert", {
        method: "POST",
        body: { token: TOKEN, target_ref: target.target_ref, rating },
      });
      if (v.ok === false) { toast(v.error, true); return refresh(); }
      render(v);
    } catch (e) {
      toast("送信に失敗しました。", true);
      $("#submit").disabled = false;
    }
  };
}

// ---- 画面: 事後アンケート（暫定設問 US-P06, Negotiable）----
function renderSurvey(view) {
  screen().innerHTML = `
    <h1>事後アンケート</h1>
    <p class="muted">最後に、分析のためのアンケートにご回答ください。</p>
    <label class="field" for="experience">なぞかけ経験</label>
    <select id="experience" data-testid="survey-experience-input">
      <option value="">選択してください</option>
      <option value="none">ほとんどない</option>
      <option value="some">ときどき触れる</option>
      <option value="frequent">よく親しんでいる</option>
    </select>
    <label class="field" for="proficiency">自己申告の熟達度（1〜5）</label>
    <select id="proficiency" data-testid="survey-proficiency-input">
      <option value="">選択してください</option>
      <option>1</option><option>2</option><option>3</option><option>4</option><option>5</option>
    </select>
    <label class="field" for="emphasis">判定時に重視した観点</label>
    <input type="text" id="emphasis" placeholder="例: 意外性、掛詞の巧みさ" data-testid="survey-emphasis-input">
    <label class="field" for="age_band">年代</label>
    <select id="age_band" data-testid="survey-age-input">
      <option value="">選択してください</option>
      <option>10s</option><option>20s</option><option>30s</option>
      <option>40s</option><option>50s</option><option>60s+</option>
    </select>
    <button class="primary" id="submit" data-testid="survey-submit-button">回答して完了する</button>
  `;
  $("#submit").onclick = async () => {
    const answers = {
      experience: $("#experience").value,
      proficiency: $("#proficiency").value,
      emphasis: $("#emphasis").value,
      age_band: $("#age_band").value,
    };
    if (!answers.experience || !answers.proficiency || !answers.age_band) {
      return toast("未回答の項目があります。", true);
    }
    $("#submit").disabled = true;
    try {
      const v = await api("/api/survey", { method: "POST", body: { token: TOKEN, answers } });
      if (v.ok === false) { toast(v.error, true); $("#submit").disabled = false; return; }
      render(v);
    } catch (e) {
      toast("送信に失敗しました。", true);
      $("#submit").disabled = false;
    }
  };
}

// ---- 画面: 完了 / エラー ----
function renderDone() {
  screen().innerHTML = `
    <div class="done-box" data-testid="done-screen">
      <h1>ご協力ありがとうございました</h1>
      <p>すべての回答が完了しました。このページは閉じていただいて構いません。</p>
    </div>`;
}

function renderError(msg) {
  screen().innerHTML = `
    <div class="error-box" data-testid="error-screen">
      <h1>アクセスできません</h1>
      <p>${escapeHtml(msg)}</p>
    </div>`;
}

async function refresh() {
  try {
    const view = await api(`/api/session?token=${encodeURIComponent(TOKEN)}`);
    render(view);
  } catch (e) {
    toast("状態の取得に失敗しました。", true);
  }
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

boot();
