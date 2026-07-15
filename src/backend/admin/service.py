"""AdminService / ExportService（LC-U3-02/03）— Repository → 純関数整形の薄い層。

集計は Repository（SQL 集約・練習除外を SQL に, BR-U3-03/09）。本モジュールは結果を
ビュー/バンドル型へ整形し、エクスポートは (本文, content-type, filename) を返す。
"""

from __future__ import annotations

from backend.admin import format as fmt
from schema import ExportBundle, ProgressView, WinrateRow


class ExportRequestError(Exception):
    """不正な format/entity（統一封筒 400 相当, BR-U3-06）。"""


# --------------------------------------------------------------- AdminService

async def get_progress(repo) -> ProgressView:
    return fmt.build_progress(await repo.read_progress())


async def get_winrates(repo) -> list[WinrateRow]:
    return fmt.build_winrates(await repo.read_winrates())


# --------------------------------------------------------------- ExportService

_ENTITIES = ("items", "judgments", "likert", "surveys")


async def build_bundle(repo, exported_at: str) -> ExportBundle:
    """全エンティティを収集して ExportBundle 正本を組む（JSON 正本）。"""
    return fmt.build_export_bundle(
        items=await repo.read_export_rows("items"),
        judgments=await repo.read_export_rows("judgments"),   # 本番のみ（SQL 保証）
        likert=await repo.read_export_rows("likert"),
        surveys=await repo.read_export_rows("surveys"),
        exported_at=exported_at,
    )


async def export(repo, fmt_kind: str, entity: str | None, exported_at: str) -> tuple[str, str, str]:
    """エクスポート本文を生成し (body, content_type, filename) を返す。

    - json（既定）: ExportBundle 全部。filename = export-bundle-<exported_at>.json
    - csv: entity 必須（items/judgments/likert/surveys）。未指定/不正は ExportRequestError。
    filename の <ts> は exported_at と同一値（監査証跡を揃える, U3 CG Q3）。
    """
    if fmt_kind == "json":
        bundle = await build_bundle(repo, exported_at)
        return (bundle.model_dump_json(), "application/json",
                f"export-bundle-{exported_at}.json")

    if fmt_kind == "csv":
        if entity not in _ENTITIES:
            raise ExportRequestError(
                "csv は entity 指定が必須（items/judgments/likert/surveys）"
            )
        rows = await repo.read_export_rows(entity)
        body = fmt.to_csv(fmt.CSV_HEADERS[entity], rows)
        return (body, "text/csv; charset=utf-8", f"export-{entity}-{exported_at}.csv")

    raise ExportRequestError("format は json か csv")
