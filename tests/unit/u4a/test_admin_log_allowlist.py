"""U4a 単体: admin_log の allowlist と実際の呼び出しの整合。

**なぜ静的走査なのか**: `admin_log` は許可外キーを**黙って落とす**（呼び出し側の規律に
依存しない秘匿の強制点）。この「黙って」が裏目に出て、**U5 と U6 で計 13 フィールドが
記録されないまま通っていた**——

  - U5: `item_ids` を渡していたが allowlist は `item_id`（単数）だけ
        → **どの作品を出題停止したかが記録されない**（著作権対応の証跡が空）
  - U6: `plan_set` / `content_hash` など全滅
        → **「コミットされたものが投入された」という証跡（DP-U6-07）が成立しない**

例示テストでは「そのイベントを書いた人が思いつくフィールド」しか守れない。**全呼び出しを
走査して漏れを検出**するのが、この失敗モードに対する正しい網。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from backend.admin.log import _ALLOWED

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src"

# ログに出してはいけないもの（秘匿方針の本体）。
_FORBIDDEN = {"token", "body", "tokens", "bodies"}


def _admin_log_kwargs() -> dict[str, set[str]]:
    """src 配下の `admin_log(...)` 呼び出しで使われているキーワード引数を集める。"""
    used: dict[str, set[str]] = {}
    for path in _SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "admin_log":
                for kw in node.keywords:
                    if kw.arg:                       # **kwargs 展開は対象外
                        used.setdefault(kw.arg, set()).add(path.name)
    return used


def test_every_logged_field_is_allowlisted():
    """★渡しているのに allowlist に無いフィールドが存在しない。

    失敗したら「ログに出ているつもりで落ちている」——`_ALLOWED` に追加すること
    （**秘匿すべきキーなら渡す側を直す**）。
    """
    used = _admin_log_kwargs()
    assert used, "admin_log の呼び出しが 1 つも見つからない（走査が壊れている）"

    dropped = {k: sorted(v) for k, v in used.items() if k not in _ALLOWED}
    assert not dropped, f"★黙って落ちているフィールド: {dropped}"


def test_allowlist_never_admits_secrets():
    """トークン生値・作品本文は**構造的に**受け付けない（秘匿の強制点）。"""
    assert _ALLOWED.isdisjoint(_FORBIDDEN), "秘匿すべきキーが allowlist に入っている"


@pytest.mark.parametrize("field", ["item_ids", "plan_set", "content_hash"])
def test_audit_trail_fields_are_recorded(field):
    """★証跡の中核フィールドが記録される。

    - `item_ids`  : U5 — 著作権配慮で**いつ何を止めたか**が問われうる
    - `plan_set` / `content_hash` : U6 — **どのプランで実験したか**の同一性
    """
    assert field in _ALLOWED


def test_admin_log_drops_unknown_and_keeps_known(monkeypatch):
    """挙動そのもの: 既知は通し、未知は落とす。"""
    captured = {}
    import backend.admin.log as mod

    monkeypatch.setattr(mod, "emit", lambda e, lv, **f: captured.update(f))
    mod.admin_log("t", "info", plan_set="primary", content_hash="abc", token="SECRET")

    assert captured.get("plan_set") == "primary"
    assert captured.get("content_hash") == "abc"
    assert "token" not in captured, "トークンが漏れている"
