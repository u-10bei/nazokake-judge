"""U4a 単体: 管理 API クライアントの User-Agent。

**なぜ固定するのか**: urllib の既定 UA `Python-urllib/x.y` は Cloudflare のエッジで
**error 1010（ブラウザ署名によるブロック）** の対象になり、デプロイ済み Worker
（*.workers.dev）への POST が **403 で弾かれる**。dev=localhost ではエッジを通らない
ため露見せず、**本番前スモーク（staging）で初めて発覚**した。

→ 一次ツールとして独自 UA を名乗る。既定 UA に戻る回帰を防ぐ。
"""

from __future__ import annotations

import json

import pytest

from scripts import _client


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_post_json_sends_non_default_user_agent(monkeypatch):
    """★POST が **`Python-urllib` でない** User-Agent を送る（Cloudflare 1010 回避）。"""
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["ua"] = req.get_header("User-agent")
        return _FakeResp(b'{"ok": true}')

    monkeypatch.setenv("ADMIN_BASIC_USER", "u")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "p")
    monkeypatch.setattr(_client.urllib.request, "urlopen", fake_urlopen)

    assert _client.post_json("http://x/admin/items", {"a": 1}) == {"ok": True}
    ua = captured["ua"]
    assert ua, "User-Agent が未設定（urllib 既定 Python-urllib に戻る）"
    assert "python-urllib" not in ua.lower(), f"既定 UA に戻っている: {ua}"


def test_auth_and_content_type_still_present(monkeypatch):
    """UA 追加で既存ヘッダ（Basic 認証・content-type）を壊していないこと。"""
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["auth"] = req.get_header("Authorization")
        seen["ct"] = req.get_header("Content-type")
        return _FakeResp(b"{}")

    monkeypatch.setenv("ADMIN_BASIC_USER", "u")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "p")
    monkeypatch.setattr(_client.urllib.request, "urlopen", fake_urlopen)

    _client.post_json("http://x/admin/items", {})
    assert seen["auth"].startswith("Basic ")
    assert seen["ct"] == "application/json"
