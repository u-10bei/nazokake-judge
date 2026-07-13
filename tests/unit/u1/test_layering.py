"""層の逆流禁止（U1-NFR-15）: U1 の下位モジュールが上位/I-O へ依存しないことを静的検証。

- schema/ は何も依存しない（最下層）。
- backend/domain/ は schema のみ（backend.repo・participant/admin/scripts へ依存しない）。
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]

# import 行から対象モジュール名を拾う簡易パターン。
_IMPORT = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.MULTILINE)


def _imported_modules(pkg_dir: pathlib.Path) -> set[str]:
    mods: set[str] = set()
    for py in pkg_dir.rglob("*.py"):
        for m in _IMPORT.findall(py.read_text(encoding="utf-8")):
            mods.add(m)
    return mods


def test_schema_has_no_project_dependencies():
    """schema/ は backend / scripts / participant / admin を import しない。"""
    mods = _imported_modules(ROOT / "schema")
    forbidden = {m for m in mods if m.split(".")[0] in {"backend", "scripts"}}
    assert not forbidden, f"schema/ が上位を import している: {forbidden}"


def test_domain_depends_only_on_schema():
    """backend/domain/ は schema のみ（repo・上位ユニットへ依存しない）。"""
    mods = _imported_modules(ROOT / "backend" / "domain")
    for m in mods:
        head = m.split(".")[0]
        assert head not in {"scripts"}, f"domain が scripts に依存: {m}"
        # 同一パッケージ内の I/O 境界（backend.repo）や上位ユニットへ依存しない。
        assert not m.startswith("backend.repo"), f"domain が repo に依存: {m}"
        assert not m.startswith("backend.participant"), f"domain が participant に依存: {m}"
        assert not m.startswith("backend.admin"), f"domain が admin に依存: {m}"
