# -*- coding: utf-8 -*-
"""交付物签名下载链接测试。

背景：浏览器直接点击 markdown 下载链接不带 JWT 头，原路由必然 401
（"未登录或登录已过期"）。修复采用 presigned URL 模式：工具生成链接时
附加 HMAC 签名 + 过期时间，路由验证签名放行；无签名回退登录鉴权。
"""

import time
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from core.deliverables.download_links import (
    sign_deliverable_query,
    verify_deliverable_signature,
)


class TestSignatureHelper:
    def test_sign_then_verify_roundtrip(self):
        filename = "table_赛力斯（601127）营收预测_20260915_174922.xlsx"
        query = sign_deliverable_query(filename)
        assert query.startswith("exp=")
        parts = dict(p.split("=", 1) for p in query.split("&"))
        assert verify_deliverable_signature(filename, parts["exp"], parts["sig"]) is True

    def test_wrong_filename_rejected(self):
        """签名与文件名绑定：拿 A 文件的签名访问 B 文件必须拒绝。"""
        query = sign_deliverable_query("table_a.xlsx")
        parts = dict(p.split("=", 1) for p in query.split("&"))
        assert verify_deliverable_signature("table_b.xlsx", parts["exp"], parts["sig"]) is False

    def test_expired_rejected(self):
        exp = str(int(time.time()) - 10)
        with patch("core.deliverables.download_links._compute_sig") as mock_sig:
            mock_sig.return_value = "0" * 32
            assert verify_deliverable_signature("a.xlsx", exp, "0" * 32) is False

    def test_missing_params_rejected(self):
        assert verify_deliverable_signature("a.xlsx", None, None) is False
        assert verify_deliverable_signature("a.xlsx", "123", None) is False
        assert verify_deliverable_signature("a.xlsx", None, "abc") is False

    def test_tampered_sig_rejected(self):
        query = sign_deliverable_query("a.xlsx")
        parts = dict(p.split("=", 1) for p in query.split("&"))
        bad_sig = ("0" if parts["sig"][0] != "0" else "1") + parts["sig"][1:]
        assert verify_deliverable_signature("a.xlsx", parts["exp"], bad_sig) is False

    def test_ascii_filename_also_works(self):
        """估值工具的纯 ASCII 文件名（valuation_601127_xxx.xlsx）同样可签名。"""
        query = sign_deliverable_query("valuation_601127_20260915_120000.xlsx")
        parts = dict(p.split("=", 1) for p in query.split("&"))
        assert (
            verify_deliverable_signature("valuation_601127_20260915_120000.xlsx", parts["exp"], parts["sig"])
            is True
        )


class TestDownloadRouteAuth:
    """下载路由双通道鉴权：签名有效放行 / 无签名要求登录。"""

    @pytest.fixture
    def client_with_file(self):
        """创建测试文件并返回 TestClient 工厂（settings 已配置）。"""
        import os
        from pathlib import Path

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        filename = "table_测试签名下载_20260915_000000.xlsx"
        base_dir = Path.cwd() / "data" / "deliverables"
        base_dir.mkdir(parents=True, exist_ok=True)
        file_path = base_dir / filename
        file_path.write_bytes(b"PK\x03\x04 fake-xlsx")

        import sys

        sys.path.insert(0, ".")
        from starlette.middleware.sessions import SessionMiddleware

        from app.routers.intelligent_assistant import router

        app = FastAPI()
        # get_current_user 访问 request.session，需要 SessionMiddleware（与主应用一致）
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        app.include_router(router)
        client = TestClient(app)

        yield client, filename

        try:
            os.remove(file_path)
        except OSError:
            pass

    def test_signed_link_downloads_without_jwt(self, client_with_file):
        """核心回归场景：浏览器直接点击签名链接（无 Authorization 头）应 200。"""
        from urllib.parse import quote

        client, filename = client_with_file
        url = f"/api/assistant/deliverables/{quote(filename)}?{sign_deliverable_query(filename)}"
        resp = client.get(url)
        assert resp.status_code == 200, f"签名链接应放行，实际 {resp.status_code}: {resp.text[:200]}"
        assert resp.content.startswith(b"PK")

    def test_unsigned_link_returns_401(self, client_with_file):
        """无签名且未登录 → 401（保持原有安全行为）。"""
        from urllib.parse import quote

        client, filename = client_with_file
        resp = client.get(f"/api/assistant/deliverables/{quote(filename)}")
        assert resp.status_code == 401

    def test_path_traversal_still_blocked(self):
        """安全回归：路径穿越必须仍然被拦截。"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from starlette.middleware.sessions import SessionMiddleware

        import sys

        sys.path.insert(0, ".")
        from app.routers.intelligent_assistant import router

        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        app.include_router(router)
        client = TestClient(app)

        # ..%2F 穿越在 path param 解码后包含 ".."，正则放行 ".." 但显式排除
        resp = client.get("/api/assistant/deliverables/..%2Fsecret.xlsx")
        assert resp.status_code in (400, 404)

    def test_non_xlsx_blocked(self, client_with_file):
        from urllib.parse import quote

        client, _ = client_with_file
        fn = "table_恶意.exe"
        url = f"/api/assistant/deliverables/{quote(fn)}?{sign_deliverable_query(fn)}"
        resp = client.get(url)
        assert resp.status_code == 400


class TestToolLinkGeneration:
    """工具返回的 markdown 链接必须带签名参数。"""

    def test_export_tool_link_contains_signature(self, monkeypatch, tmp_path):
        from core.tools.implementations.assistant_ops import export_table_excel_tool as mod

        monkeypatch.setattr(mod, "_OUTPUT_DIR", str(tmp_path))

        markdown = (
            "| 月份 | 销量 | 营收(亿) |\n|---|---:|---:|\n| 2026-09 | 10,500 | 106.5 |"
        )
        result = mod.export_table_excel_tool.invoke(
            {"markdown_tables": f"## 营收预测\n{markdown}", "title": "赛力斯（601127）营收预测"}
        )
        assert "exp=" in result and "sig=" in result
        # 半角括号不得出现在链接中（markdown 链接目标会截断）
        assert "(" not in result.split("](")[-1]

    def test_filename_fullwidth_parens(self):
        from core.tools.implementations.assistant_ops.export_table_excel_tool import (
            _sanitize_filename_part,
        )

        assert "(" not in _sanitize_filename_part("赛力斯(601127)模型")
        assert "（601127）" in _sanitize_filename_part("赛力斯(601127)模型")
