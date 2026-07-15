"""U3 純粋整形の単体テスト（DP-U3-04 / U3-NFR-09）。

重点は **CSV エスケープ**（U3 唯一の間違えうる整形ロジック・標準 csv モジュール）と、
winrate 定義（wins/matches, matches=0→0）・ExportBundle 組立の構造。
"""

from __future__ import annotations

import csv
import io

from backend.admin import format as fmt
from schema import EXPORT_FORMAT_VERSION


def test_to_csv_rfc4180_escaping():
    """カンマ・引用符・改行・日本語を含む値が RFC4180 準拠で往復する。"""
    headers = ["item_id", "layer"]
    rows = [
        {"item_id": "a,b", "layer": "pro"},          # カンマ
        {"item_id": 'q"x', "layer": "ai"},           # 引用符
        {"item_id": "line1\nline2", "layer": "edit"},  # 改行
        {"item_id": "謎かけ", "layer": "rule"},        # 日本語
    ]
    out = fmt.to_csv(headers, rows)
    # 標準 csv で読み戻して一致（エスケープの正しさ＝往復で担保）。
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed[0] == headers
    assert parsed[1] == ["a,b", "pro"]
    assert parsed[2] == ['q"x', "ai"]
    assert parsed[3] == ["line1\nline2", "edit"]
    assert parsed[4] == ["謎かけ", "rule"]


def test_to_csv_missing_and_dict_cells():
    """欠損は空文字、dict/list セル（surveys.answers）は JSON 文字列化。"""
    out = fmt.to_csv(["token", "answers"], [{"token": "t1", "answers": {"age_band": "30s"}}])
    parsed = list(csv.reader(io.StringIO(out)))
    assert parsed[1][0] == "t1"
    assert '"age_band"' in parsed[1][1] or "age_band" in parsed[1][1]
    out2 = fmt.to_csv(["a", "b"], [{"a": "x"}])   # b 欠損
    assert list(csv.reader(io.StringIO(out2)))[1] == ["x", ""]


def test_build_winrates_definition():
    """winrate = wins/matches、matches=0 は winrate=0。"""
    rows = [
        {"item_id": "i1", "layer": "pro", "matches": 4, "wins": 3},
        {"item_id": "i2", "layer": "ai", "matches": 0, "wins": 0},
    ]
    wr = {r.item_id: r for r in fmt.build_winrates(rows)}
    assert abs(wr["i1"].winrate - 0.75) < 1e-9
    assert wr["i2"].winrate == 0.0
    assert wr["i2"].matches == 0


def test_build_progress():
    view = fmt.build_progress({
        "tokens_issued": 10, "tokens_started": 7, "tokens_completed": 5,
        "judgments_total": 200, "likert_total": 50, "survey_total": 5,
    })
    assert view.tokens_issued == 10 and view.judgments_total == 200


def test_build_export_bundle_structure_and_selfcontained():
    """ExportBundle: schema_version 付与・body 非含有・judgments の item ⊆ items。"""
    items = [{"item_id": "i1", "layer": "pro"}, {"item_id": "i2", "layer": "ai"}]
    judgments = [{
        "token": "t1", "pair_id": "p0", "pair_index": 0,
        "item_left": "i1", "item_right": "i2", "choice": "A",
        "created_at": "2026-07-15T00:00:00Z",
    }]
    surveys = [{"token": "t1", "answers": '{"age_band":"30s"}',
                "created_at": "2026-07-15T00:00:00Z"}]
    bundle = fmt.build_export_bundle(
        items=items, judgments=judgments, likert=[], surveys=surveys,
        exported_at="2026-07-15T01:00:00Z")
    assert bundle.schema_version == EXPORT_FORMAT_VERSION
    assert bundle.exported_at == "2026-07-15T01:00:00Z"
    # body は型に存在しない（ExportItem は item_id/layer のみ）。
    assert not hasattr(bundle.items[0], "body")
    # 自己完結: judgments の item は items に含まれる。
    item_ids = {it.item_id for it in bundle.items}
    for j in bundle.judgments:
        assert j.item_left in item_ids and j.item_right in item_ids
    # answers が JSON 文字列でも dict に復元される。
    assert bundle.surveys[0].answers == {"age_band": "30s"}
