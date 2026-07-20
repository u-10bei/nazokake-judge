"""U6 単体: plan_ingest の★ハッシュ照合（DP-U6-07）。

**責務の境界**: POST の成否・409 ガードは実 D1 の integration が正。ここでは
**ネットワークなしで確かめられる照合ロジック**——「何を検出できるか」を固定する。
"""

from __future__ import annotations

import json

import pytest

from scripts import plan_ingest
from scripts.plan_generate.verify import content_hash


def _write(tmp_path, rows, meta_overrides=None):
    d = tmp_path / "primary"
    d.mkdir()
    lk = ["i003", "i007"]
    meta = {"plan_set": "primary", "seed": 20260720, "attempt": 0,
            "content_hash": content_hash(rows, lk), "n_items": 10, "n_slots": 2,
            "n_pairs": 12, "m_per_item": 4, "likert_targets": lk,
            "generated_at": "2026-07-20T00:00:00Z"}
    meta.update(meta_overrides or {})
    (d / "plan.json").write_text(json.dumps(rows), encoding="utf-8")
    (d / "plan.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


ROWS = [{"plan_index": 0, "idx": 0, "item_left": "i001", "item_right": "i002",
         "is_practice": True},
        {"plan_index": 0, "idx": 1, "item_left": "i003", "item_right": "i004",
         "is_practice": False}]


def test_hash_uses_the_same_implementation_as_the_generator():
    """★照合は `plan_generate` と**同一の実装**を使う。

    再実装すると「自分が計算したものと自分が計算したものが一致する」だけになり、
    **生成器とのずれを検出できない**——照合が自己満足になる。
    """
    from scripts.plan_generate.__main__ import content_hash as generator_hash
    assert plan_ingest.content_hash is generator_hash


def test_tampered_plan_is_rejected_before_posting(tmp_path, monkeypatch, capsys):
    """★`plan.json` が改竄されていたら**POST せずに** exit 1（手直し・マージ事故）。"""
    d = _write(tmp_path, ROWS)
    rows = json.loads((d / "plan.json").read_text(encoding="utf-8"))
    rows[1]["item_left"] = "i099"                      # 1 箇所だけ書き換える
    (d / "plan.json").write_text(json.dumps(rows), encoding="utf-8")

    posted = []
    monkeypatch.setattr(plan_ingest, "_post", lambda u, p: posted.append(u) or {"ok": True})
    rc = plan_ingest.main([str(d), "--base-url", "http://x"])

    assert rc == 1
    assert posted == [], "★照合に失敗したのに POST している"
    assert "一致しません" in capsys.readouterr().err


def test_mismatched_meta_and_plan_are_rejected(tmp_path, monkeypatch, capsys):
    """★`likert_targets` だけが違う（= メタと行が別々の生成実行に由来）ケースも検出。

    行だけを比べていると通ってしまう——ハッシュが `likert_targets` を含む理由。
    """
    d = _write(tmp_path, ROWS, meta_overrides={"likert_targets": ["i003", "i099"]})
    posted = []
    monkeypatch.setattr(plan_ingest, "_post", lambda u, p: posted.append(u) or {"ok": True})
    assert plan_ingest.main([str(d), "--base-url", "http://x"]) == 1
    assert posted == []


def test_valid_plan_is_posted(tmp_path, monkeypatch):
    """整合していれば投入する（`--activate` なしでは activate を叩かない）。"""
    d = _write(tmp_path, ROWS)
    calls = []

    def fake(url, payload):
        calls.append(url)
        return {"ok": True, "rows": len(payload.get("rows", [])),
                "content_hash": payload.get("meta", {}).get("content_hash")}

    monkeypatch.setattr(plan_ingest, "_post", fake)
    assert plan_ingest.main([str(d), "--base-url", "http://x"]) == 0
    assert calls == ["http://x/admin/plan"], "activate まで叩いている"


def test_activate_flag_posts_both(tmp_path, monkeypatch):
    """`--activate` で投入 → 有効化の 2 本を**この順序で**叩く。"""
    d = _write(tmp_path, ROWS)
    calls = []
    monkeypatch.setattr(plan_ingest, "_post",
                        lambda u, p: calls.append(u) or {"ok": True, "rows": 2})
    assert plan_ingest.main([str(d), "--activate", "--base-url", "http://x"]) == 0
    assert calls == ["http://x/admin/plan", "http://x/admin/plan/activate"]


def test_server_hash_disagreement_fails(tmp_path, monkeypatch, capsys):
    """★サーバが記録したハッシュが違えば失敗（投入経路での取り違えを閉じる）。"""
    d = _write(tmp_path, ROWS)
    monkeypatch.setattr(plan_ingest, "_post",
                        lambda u, p: {"ok": True, "rows": 2, "content_hash": "deadbeef"})
    assert plan_ingest.main([str(d), "--base-url", "http://x"]) == 1
    assert "サーバ記録のハッシュ" in capsys.readouterr().err


@pytest.mark.parametrize("flag", ["--activate", "--activate-only"])
def test_409_guidance_on_both_activate_paths(tmp_path, monkeypatch, capsys, flag):
    """★409 の案内が**両経路**で出る（片方だけだと運用者が理由を追えない）。

    運用上 409 に当たりやすいのはむしろ `--activate-only`（収集開始後に「まだ有効化して
    いなかった」と気づく順序）。
    """
    d = _write(tmp_path, ROWS)

    def fake(url, payload):
        if url.endswith("/activate"):
            return {"ok": False, "status": 409, "error": "収集開始後の切替は拒否されました"}
        return {"ok": True, "rows": 2}

    monkeypatch.setattr(plan_ingest, "_post", fake)
    assert plan_ingest.main([str(d), flag, "--base-url", "http://x"]) == 1
    assert "収集開始後の切替は不可" in capsys.readouterr().err


def test_missing_files_give_actionable_error(tmp_path):
    """ファイル不在は**次に打つコマンドつき**で失敗する。"""
    with pytest.raises(SystemExit) as e:
        plan_ingest.main([str(tmp_path / "nosuch"), "--base-url", "http://x"])
    assert "plan_generate" in str(e.value)
