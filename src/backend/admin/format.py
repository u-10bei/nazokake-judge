"""純粋整形（DP-U3-04）— Repository 集計行 → ビュー/バンドル型・CSV。

副作用なし・D1 非依存＝example ベース単体テスト可能（U3-NFR-09）。
CSV は**標準 `csv` モジュール**（`io.StringIO` + `csv.writer`）で RFC4180 準拠出力（U3 CG Q3）。
"""

from __future__ import annotations

import csv
import io
import json

from schema import (
    EXPORT_FORMAT_VERSION,
    ExportBundle,
    ExportItem,
    ExportJudgment,
    ExportLikert,
    ExportSurvey,
    ProgressView,
    WinrateRow,
)


# ----------------------------------------------------------------- ビュー整形

def build_progress(row: dict) -> ProgressView:
    return ProgressView(
        tokens_issued=row["tokens_issued"],
        tokens_started=row["tokens_started"],
        tokens_completed=row["tokens_completed"],
        judgments_total=row["judgments_total"],
        likert_total=row["likert_total"],
        survey_total=row["survey_total"],
    )


def build_winrates(rows: list[dict]) -> list[WinrateRow]:
    out: list[WinrateRow] = []
    for r in rows:
        matches = int(r["matches"])
        wins = int(r["wins"])
        winrate = (wins / matches) if matches > 0 else 0.0
        out.append(WinrateRow(
            item_id=r["item_id"], layer=r["layer"],
            matches=matches, wins=wins, winrate=winrate,
        ))
    return out


# ----------------------------------------------------------------- エクスポート

def build_export_bundle(
    *, items: list[dict], judgments: list[dict], likert: list[dict],
    surveys: list[dict], exported_at: str,
) -> ExportBundle:
    """ExportBundle 正本を組む（BR-U3-07）。judgments は本番のみ（呼び出し側で保証）。"""
    return ExportBundle(
        schema_version=EXPORT_FORMAT_VERSION,
        exported_at=exported_at,
        items=[ExportItem(item_id=r["item_id"], layer=r["layer"]) for r in items],
        judgments=[
            ExportJudgment(
                token=r["token"], pair_id=r["pair_id"], pair_index=r["pair_index"],
                item_left=r["item_left"], item_right=r["item_right"],
                choice=r["choice"], created_at=r["created_at"],
            ) for r in judgments
        ],
        likert=[
            ExportLikert(token=r["token"], target_ref=r["target_ref"],
                         rating=r["rating"], created_at=r["created_at"])
            for r in likert
        ],
        surveys=[
            ExportSurvey(token=r["token"],
                         answers=_load_answers(r["answers"]),
                         created_at=r["created_at"])
            for r in surveys
        ],
    )


# entity → CSV ヘッダ（列順を固定）。
CSV_HEADERS = {
    "items": ["item_id", "layer"],
    "judgments": ["token", "pair_id", "pair_index", "item_left", "item_right",
                  "choice", "created_at"],
    "likert": ["token", "target_ref", "rating", "created_at"],
    "surveys": ["token", "answers", "created_at"],
}


def to_csv(headers: list[str], rows: list[dict]) -> str:
    """行 dict 列を RFC4180 準拠 CSV へ（標準 csv モジュール, U3 CG Q3）。

    surveys の answers（dict）は JSON 文字列に落として 1 セルに収める。
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in rows:
        writer.writerow([_cell(r.get(h)) for h in headers])
    return buf.getvalue()


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _load_answers(raw) -> dict:
    """survey_responses.answers（D1 上は JSON 文字列）を dict へ。"""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw) if raw else {}
        return parsed if isinstance(parsed, dict) else {"_raw": parsed}
    except (ValueError, TypeError):
        return {}
