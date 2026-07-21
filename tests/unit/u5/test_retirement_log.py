"""U5 単体: 出題停止の証跡ファイル（著作権対応の「いつ・何を・なぜ」）。

**なぜ CLI 側に証跡が要るのか**: サーバの `admin_log` は `wrangler tail` で**追っている間
だけ**流れ、**永続化されない**。「廃止履歴の正は admin_log」という当初の想定は、後から
示せる記録としては成立しない——追っていなければ何も残らないため。
"""

from __future__ import annotations

import json

import pytest

from scripts import pool_retire


@pytest.fixture
def _api(monkeypatch):
    """管理 API を差し替える（ネットワークなし）。"""
    calls = []

    def fake_post(url, payload):
        calls.append((url, payload))
        return {"ok": True, "retired": len(payload["item_ids"]),
                "already_retired": [], "not_found": []}

    monkeypatch.setattr(pool_retire, "post_json", fake_post)
    monkeypatch.setattr(pool_retire, "base_url", lambda x: "http://x")
    return calls


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_retire_writes_audit_record(tmp_path, _api):
    """★停止操作が「いつ・何を・なぜ」を残す。"""
    log = tmp_path / "retirement-log.jsonl"
    rc = pool_retire.main(["N01", "N02", "--reason", "著作権配慮", "--log", str(log)])

    assert rc == 0
    (rec,) = _records(log)
    assert rec["action"] == "retire"
    assert rec["item_ids"] == ["N01", "N02"]        # ★どの作品を止めたか
    assert rec["reason"] == "著作権配慮"              # ★なぜ止めたか
    assert rec["at"].startswith("20")                # ★いつ止めたか（ISO8601 UTC）
    assert rec["changed"] == 2


def test_records_are_appended_not_overwritten(tmp_path, _api):
    """★追記型——過去の証跡を上書きしない（履歴が消えたら証跡にならない）。"""
    log = tmp_path / "retirement-log.jsonl"
    pool_retire.main(["N01", "--reason", "r1", "--log", str(log)])
    pool_retire.main(["N02", "--reason", "r2", "--log", str(log)])
    pool_retire.main(["N01", "--unretire", "--reason", "r3", "--log", str(log)])

    recs = _records(log)
    assert [r["action"] for r in recs] == ["retire", "retire", "unretire"]
    assert [r["item_ids"] for r in recs] == [["N01"], ["N02"], ["N01"]]


def test_no_body_in_record(tmp_path, _api):
    """作品本文は証跡に入らない（`item_id` のみ）＝**だからコミットしてよい**。"""
    log = tmp_path / "retirement-log.jsonl"
    pool_retire.main(["N01", "--reason", "x", "--log", str(log)])
    (rec,) = _records(log)
    assert set(rec) == {"at", "action", "item_ids", "reason", "changed",
                        "already", "not_found", "target"}
    assert "body" not in rec


def test_missing_reason_warns_but_still_records(tmp_path, _api, capsys):
    """`--reason` 未指定でも**記録は残す**（残らないより残る方が良い）。ただし警告する。"""
    log = tmp_path / "retirement-log.jsonl"
    pool_retire.main(["N01", "--log", str(log)])

    (rec,) = _records(log)
    assert rec["reason"] is None
    assert "--reason が未指定" in capsys.readouterr().err


def test_no_log_flag_suppresses(tmp_path, _api):
    """`--no-log` で抑止できる（非推奨だが dev の試行で汚したくない場合）。"""
    log = tmp_path / "retirement-log.jsonl"
    pool_retire.main(["N01", "--no-log", "--log", str(log)])
    assert not log.exists()
