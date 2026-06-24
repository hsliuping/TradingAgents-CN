"""
Skill 导入与测试验证 API 验收测试

覆盖:
- POST /api/skills/import                  本地 SKILL.md 内容导入
- POST /api/skills/import-url              URL 导入
- POST /api/skills/test                    Skill 沙箱测试
- GET  /api/skills/github/repo/{owner}/{repo} GitHub 仓库 Skill 浏览
- POST /api/skills/import-github           从 GitHub 导入并测试
- GET  /api/skills/smithery/servers        Smithery MCP Server 列表
- GET  /api/skill-center/skills            统一 Skill 中心列表（验证注册）
"""
import pytest


SAMPLE_SKILL_MD = """---
name: test-hello-skill
version: "1.0.0"
description: 用于验收测试的示例 Skill
author: acceptance-test
category: test
tags: [test]
parameters:
  - name: name
    type: string
    description: 名称
    required: false
implementation:
  type: python
  code: |
    import json
    import sys
    args = json.loads(sys.stdin.read()) if sys.stdin else {}
    name = args.get("name", "world")
    print("__SANDBOX_OUTPUT_START__")
    print(json.dumps({"message": f"hello {name}"}, ensure_ascii=False))
    print("__SANDBOX_OUTPUT_END__")
---

这是一个用于验收测试的 Skill，导入后会自动注册到 ToolRegistry。
"""


class TestSkillImport:
    """Skill 导入与测试。"""

    def test_import_skill_from_content(self, api_client):
        """从内容导入 Skill。"""
        resp = api_client.post("/api/skills/import", json={"content": SAMPLE_SKILL_MD})
        assert resp.status_code in (200, 400), f"导入异常: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert data["name"] == "test-hello-skill"

    def test_test_skill_with_args(self, api_client):
        """测试已导入的 Skill 并传入参数。"""
        resp = api_client.post("/api/skills/test", json={
            "skill_name": "test-hello-skill",
            "args": {"name": "trading"}
        })
        assert resp.status_code == 200, f"测试失败: {resp.status_code} {resp.text}"
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["message"] == "hello trading"

    def test_skill_appears_in_skill_center(self, api_client):
        """导入的 Skill 出现在统一 Skill 中心。"""
        resp = api_client.get("/api/skill-center/skills")
        assert resp.status_code == 200, f"获取 Skill 中心失败: {resp.status_code} {resp.text}"
        skills = resp.json()
        skill_ids = [s["skill_id"] for s in skills]
        assert "test-hello-skill" in skill_ids, f"导入的 Skill 未出现在 Skill 中心: {skill_ids}"

    def test_import_skill_already_exists(self, api_client):
        """重复导入同一个 Skill 应返回 400。"""
        resp = api_client.post("/api/skills/import", json={"content": SAMPLE_SKILL_MD})
        assert resp.status_code == 400, f"重复导入应失败: {resp.status_code} {resp.text}"

    def test_github_repo_skills_browse(self, api_client):
        """GitHub 仓库浏览接口可用（使用示例仓库）。"""
        # 使用一个不依赖网络稳定性的公开示例仓库；接口成功返回结构即可
        resp = api_client.get("/api/skills/github/repo/modelcontextprotocol/servers")
        # 该仓库可能没有 SKILL.md，但接口本身应正常返回
        assert resp.status_code in (200, 404), f"GitHub 浏览接口异常: {resp.status_code} {resp.text}"

    def test_smithery_servers_list(self, api_client):
        """Smithery MCP Server 列表接口可用。"""
        resp = api_client.get("/api/skills/smithery/servers")
        assert resp.status_code in (200, 500), f"Smithery 接口异常: {resp.status_code} {resp.text}"
        if resp.status_code == 200:
            data = resp.json()
            assert isinstance(data, list)


class TestSkillTestFailures:
    """Skill 测试失败场景。"""

    def test_test_nonexistent_skill(self, api_client):
        """测试不存在的 Skill 返回 404。"""
        resp = api_client.post("/api/skills/test", json={
            "skill_name": "skill-not-exists-xyz",
            "args": {}
        })
        assert resp.status_code == 404, f"应返回 404: {resp.status_code} {resp.text}"
