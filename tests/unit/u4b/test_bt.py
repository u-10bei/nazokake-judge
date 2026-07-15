"""U4b 単体（example）: CLI 入出力・版検証（PU4b-7）・終了コード契約・U3 突合（PU4b-6）・
較正の閉形式・rank 同値処理。

CLI は temp file 越しに main() を呼び、終了コードと出力を検証する（DP-U4b-03）。
"""

from __future__ import annotations

import json

import pytest

from schema import EXPORT_FORMAT_VERSION, ExportBundle, ExportItem, ExportJudgment, ExportLikert

from scripts.bt_aggregate.__main__ import EXIT_FAIL, EXIT_OK, aggregate_bundle, main
from scripts.bt_aggregate.calibrate import calibrate, calibrated_score


# --------------------------------------------------------------- ヘルパ
def _jud(idx, left, right, choice):
    return ExportJudgment(token=f"t{idx}", pair_id=f"p{idx}", pair_index=idx,
                          item_left=left, item_right=right, choice=choice,
                          created_at="2026-07-15T00:00:00Z")


def _bundle(items, judgments, likert=None, schema_version=None):
    return ExportBundle(
        schema_version=schema_version or EXPORT_FORMAT_VERSION,
        exported_at="2026-07-15T00:00:00Z",
        items=items, judgments=judgments, likert=likert or [], surveys=[],
    )


def _write(tmp_path, bundle, name="export.json"):
    p = tmp_path / name
    p.write_text(bundle.model_dump_json(), encoding="utf-8")
    return str(p)


# 小さな連結データ: 3 item・A>B>C の推移的勝敗。
def _sample_items():
    return [ExportItem(item_id="iA", layer="pro"),
            ExportItem(item_id="iB", layer="ai"),
            ExportItem(item_id="iC", layer="edit")]


def _sample_judgments():
    return [
        _jud(0, "iA", "iB", "A"),   # A 勝ち
        _jud(1, "iA", "iB", "A"),   # A 勝ち
        _jud(2, "iB", "iC", "A"),   # B 勝ち
        _jud(3, "iC", "iA", "B"),   # A 勝ち（右=iA）
    ]


# --------------------------------------------------------------- PU4b-6 U3 突合
def test_pu4b6_matches_wins_match_u3_definition():
    """matches/wins が U3 winrate 定義（出場数・choice=A→item_left 勝ち・生カウント）と一致。"""
    items, judgments = _sample_items(), _sample_judgments()
    result = aggregate_bundle(_bundle(items, judgments), alpha=1.0, max_iter=10000, tol=1e-10)

    # 独立に U3 定義で matches/wins を計算（同一エクスポート）。
    exp_matches = {"iA": 0, "iB": 0, "iC": 0}
    exp_wins = {"iA": 0, "iB": 0, "iC": 0}
    for j in judgments:
        exp_matches[j.item_left] += 1
        exp_matches[j.item_right] += 1
        winner = j.item_left if j.choice == "A" else j.item_right
        exp_wins[winner] += 1

    got = {s.item_id: (s.matches, s.wins) for s in result.items}
    for iid in exp_matches:
        assert got[iid] == (exp_matches[iid], exp_wins[iid]), iid
    # iA: 3 戦 3 勝（j0/j1/j3）/ iB: 3 戦 1 勝（j0/j1/j2）/ iC: 2 戦 0 勝（j2/j3）。
    assert got["iA"] == (3, 3)
    assert got["iB"] == (3, 1)
    assert got["iC"] == (2, 0)


def test_alpha_not_mixed_into_matches_wins():
    """α を変えても matches/wins（生カウント）は不変＝α は fit_bt 内部のみ（Q2 不変条件）。"""
    items, judgments = _sample_items(), _sample_judgments()
    r1 = aggregate_bundle(_bundle(items, judgments), alpha=0.5, max_iter=10000, tol=1e-10)
    r2 = aggregate_bundle(_bundle(items, judgments), alpha=2.0, max_iter=10000, tol=1e-10)
    mw1 = {s.item_id: (s.matches, s.wins) for s in r1.items}
    mw2 = {s.item_id: (s.matches, s.wins) for s in r2.items}
    assert mw1 == mw2
    # BTResult.alpha は使用値を記録（監査, DP-U4b-04）。
    assert r1.alpha == 0.5 and r2.alpha == 2.0


# --------------------------------------------------------------- PU4b-7 版検証・終了コード
def test_pu4b7_version_mismatch_is_error(tmp_path, capsys):
    path = _write(tmp_path, _bundle(_sample_items(), _sample_judgments(), schema_version="9.9.9"))
    assert main([path]) == EXIT_FAIL
    assert "schema_version 不一致" in capsys.readouterr().err


def test_pu4b7_version_mismatch_allowed_with_flag(tmp_path):
    out = tmp_path / "r.json"
    path = _write(tmp_path, _bundle(_sample_items(), _sample_judgments(), schema_version="9.9.9"))
    assert main([path, "--allow-version-mismatch", "--out", str(out)]) == EXIT_OK
    result = json.loads(out.read_text(encoding="utf-8"))
    assert any("版不一致" in w for w in result["warnings"])


def test_exit_file_not_found(capsys):
    assert main(["/nonexistent/does-not-exist.json"]) == EXIT_FAIL
    assert "見つかりません" in capsys.readouterr().err


def test_exit_bad_json(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert main([str(p)]) == EXIT_FAIL
    assert "JSON パース" in capsys.readouterr().err


def test_exit_validation_error(tmp_path, capsys):
    p = tmp_path / "invalid.json"
    p.write_text(json.dumps({"schema_version": "1.0.0"}), encoding="utf-8")  # exported_at 欠落
    assert main([str(p)]) == EXIT_FAIL
    assert "検証に失敗" in capsys.readouterr().err


def test_normal_run_exit_ok_and_json_shape(tmp_path):
    out = tmp_path / "r.json"
    path = _write(tmp_path, _bundle(_sample_items(), _sample_judgments()))
    assert main([path, "--out", str(out)]) == EXIT_OK
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["n_items"] == 3
    assert result["n_comparisons"] == 4
    assert result["source"]["schema_version"] == EXPORT_FORMAT_VERSION
    assert result["converged"] is True
    # iA が最上位（rank=1）。
    by_id = {s["item_id"]: s for s in result["items"]}
    assert by_id["iA"]["rank"] == 1
    assert by_id["iA"]["bt_score"] > by_id["iB"]["bt_score"] > by_id["iC"]["bt_score"]


# --------------------------------------------------------------- 非連結 warnings（BR-U4b-02/07）
def test_disconnected_excluded_items_visible():
    # 2 つの独立ペア: (iA,iB) と (iC,iD)。最大成分が同数の場合 item_id 列辞書順で iA 側。
    items = [ExportItem(item_id=x, layer="pro") for x in ("iA", "iB", "iC", "iD")]
    judgments = [_jud(0, "iA", "iB", "A"), _jud(1, "iC", "iD", "A")]
    result = aggregate_bundle(_bundle(items, judgments), alpha=1.0, max_iter=10000, tol=1e-10)
    assert result.n_components == 2
    assert result.estimated_component_size == 2
    by_id = {s.item_id: s for s in result.items}
    # 推定対象（iA,iB）は bt_score あり、除外（iC,iD）は null。
    assert by_id["iA"].bt_score is not None and by_id["iB"].bt_score is not None
    assert by_id["iC"].bt_score is None and by_id["iD"].bt_score is None
    # 除外でも matches/wins は残る（BR-U4b-07）。
    assert by_id["iC"].matches == 1 and by_id["iC"].wins == 1
    assert any("非連結" in w for w in result.warnings)


# --------------------------------------------------------------- rank 同値処理（Step 6 明文固定）
def test_rank_tiebreak_by_item_id():
    """θ が厳密一致する対称構造 → rank は item_id 昇順で安定順位付け。"""
    # iA と iB が完全対称（1 勝 1 敗ずつ）→ θ_A = θ_B。
    items = [ExportItem(item_id="iB", layer="pro"), ExportItem(item_id="iA", layer="pro")]
    judgments = [_jud(0, "iA", "iB", "A"), _jud(1, "iA", "iB", "B")]
    result = aggregate_bundle(_bundle(items, judgments), alpha=1.0, max_iter=10000, tol=1e-12)
    by_id = {s.item_id: s for s in result.items}
    # θ 同値。
    assert abs(by_id["iA"].bt_score - by_id["iB"].bt_score) < 1e-9
    # 同値は item_id 昇順 → iA が rank 1、iB が rank 2。
    assert by_id["iA"].rank == 1
    assert by_id["iB"].rank == 2


# --------------------------------------------------------------- 較正 example（PU4b-5 補完）
def test_calibration_closed_form_example():
    theta = {"i0": 0.0, "i1": 1.0, "i2": 2.0}   # θ = 1·L + (-1)（L=1,2,3）
    likert = [ExportLikert(token="t", target_ref=iid, rating=r, created_at="2026-07-15T00:00:00Z")
              for iid, r in (("i0", 1), ("i1", 2), ("i2", 3))]
    outcome = calibrate(theta, likert, {"i0", "i1", "i2"})
    assert outcome.skip_reason is None
    assert outcome.calibration.slope == pytest.approx(1.0)
    assert outcome.calibration.intercept == pytest.approx(-1.0)
    assert calibrated_score(theta["i2"], outcome.calibration) == pytest.approx(3.0)


def test_calibration_skips_with_one_anchor():
    theta = {"i0": 0.0, "i1": 1.0}
    likert = [ExportLikert(token="t", target_ref="i0", rating=3, created_at="2026-07-15T00:00:00Z")]
    outcome = calibrate(theta, likert, {"i0", "i1"})
    assert outcome.skip_reason == "anchors<2"
    assert outcome.calibration is None


def test_calibration_excludes_target_ref_not_in_items():
    theta = {"i0": 0.0, "i1": 1.0, "i2": 2.0}
    likert = [
        ExportLikert(token="t", target_ref="i0", rating=1, created_at="2026-07-15T00:00:00Z"),
        ExportLikert(token="t", target_ref="i1", rating=2, created_at="2026-07-15T00:00:00Z"),
        ExportLikert(token="t", target_ref="ghost", rating=5, created_at="2026-07-15T00:00:00Z"),
    ]
    outcome = calibrate(theta, likert, {"i0", "i1", "i2"})
    assert "ghost" in outcome.excluded_targets
