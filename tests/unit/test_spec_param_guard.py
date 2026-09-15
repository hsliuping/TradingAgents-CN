# -*- coding: utf-8 -*-
"""非法标识符参数（如 headers.User-Agent）防线测试。

背景：需求分析阶段 LLM 曾把 HTTP 请求头误收录为函数参数
（headers.User-Agent / headers.Referer），这类名字不可能出现在
Python 函数签名中，导致静态校验每轮必失败、Agent Loop 死循环重试。
"""

import pytest

from core.tools.external.requirement_analyzer import RequirementAnalyzer
from core.tools.external.skill_spec import GeneratedCode, SkillSpec
from core.tools.external.static_validator import StaticValidator

DCD_URL = "https://www.dongchedi.com/motor/pc/car/rank_data"


def _make_spec(params: list) -> SkillSpec:
    return SkillSpec(
        tool_id="probe_tool",
        display_name="探针",
        description="测试",
        category="market",
        data_source="dongchedi",
        parameters=params,
    )


class TestStaticValidatorInvalidParams:
    def test_invalid_param_names_skipped_in_signature_check(self):
        """含 headers.User-Agent 等伪参数时，签名对比应跳过而非报错"""
        spec = _make_spec([
            {"name": "month", "type": "string", "description": "月份", "required": True},
            {"name": "headers.User-Agent", "type": "string", "description": "UA", "required": True},
            {"name": "headers.Referer", "type": "string", "description": "Referer", "required": True},
        ])
        code = GeneratedCode(
            code="def probe_tool(month: str = '202608'):\n    return {'status': 'success', 'data': []}\n",
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert result.passed, f"应通过静态校验，错误: {result.errors}"
        assert not any("headers" in e for e in result.errors)

    def test_python_keyword_params_skipped_in_signature_check(self):
        """Python 关键字参数（class/import）同样无法出现在签名中，应跳过"""
        spec = _make_spec([
            {"name": "month", "type": "string", "description": "月份", "required": True},
            {"name": "class", "type": "string", "description": "类别", "required": True},
            {"name": "import", "type": "string", "description": "导入", "required": True},
        ])
        code = GeneratedCode(
            code="def probe_tool(month: str = '202608'):\n    return {'status': 'success', 'data': []}\n",
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert result.passed, f"应通过静态校验，错误: {result.errors}"

    def test_valid_missing_param_still_reported(self):
        """合法参数缺失时仍应正常报错（防线不豁免真实缺失）"""
        spec = _make_spec([
            {"name": "month", "type": "string", "description": "月份", "required": True},
            {"name": "count", "type": "int", "description": "数量", "required": True},
        ])
        code = GeneratedCode(
            code="def probe_tool(month: str = '202608'):\n    return {'status': 'success', 'data': []}\n",
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert not result.passed
        assert any("count" in e for e in result.errors)


class TestSpecParamSanitizer:
    def test_sanitize_drops_invalid_params_and_adds_constraint(self):
        """伪参数被剔除，头部要求转入 constraints 不丢信息"""
        data = {
            "tool_id": "t",
            "parameters": [
                {"name": "month", "type": "string", "description": "月份", "required": True},
                {"name": "headers.User-Agent", "type": "string", "description": "UA", "required": True},
                {"name": "headers.Referer", "type": "string", "description": "R", "required": True},
            ],
            "constraints": ["原有约束"],
        }
        RequirementAnalyzer._sanitize_spec_params(data)
        assert [p["name"] for p in data["parameters"]] == ["month"]
        assert len(data["constraints"]) == 2
        assert "HTTP 头" in data["constraints"][1]

    def test_sanitize_noop_for_valid_params(self):
        """全合法参数时不做任何修改"""
        data = {
            "tool_id": "t",
            "parameters": [{"name": "month", "type": "string", "description": "m", "required": True}],
            "constraints": ["c"],
        }
        RequirementAnalyzer._sanitize_spec_params(data)
        assert len(data["parameters"]) == 1
        assert data["constraints"] == ["c"]

    def test_sanitize_drops_python_keyword_params(self):
        """Python 关键字参数（class）同样被剔除"""
        data = {
            "tool_id": "t",
            "parameters": [
                {"name": "month", "type": "string", "description": "m", "required": True},
                {"name": "class", "type": "string", "description": "类别", "required": True},
            ],
            "constraints": [],
        }
        RequirementAnalyzer._sanitize_spec_params(data)
        assert [p["name"] for p in data["parameters"]] == ["month"]
        assert len(data["constraints"]) == 1


class TestInterfaceSpecGuard:
    """接口规格（URL）从对话到代码的全链路防线"""

    CONVERSATION = (
        "用户需求：懂车帝车型月销量查询\n"
        f"GET `{DCD_URL}?month=202608&rank_data_type=11&count=100&offset=0`\n"
        "请求头：User-Agent + Referer 即可，无需认证。\n"
    )

    def test_ensure_interface_spec_constraints_extracts_url(self):
        """对话含 URL 但 LLM 输出 constraints 为空时，兜底写入 URL 与请求头"""
        data = {"tool_id": "t", "parameters": [], "constraints": []}
        RequirementAnalyzer._ensure_interface_spec_constraints(data, self.CONVERSATION)
        joined = "\n".join(data["constraints"])
        assert DCD_URL in joined
        assert "严禁改写" in joined
        assert "User-Agent" in joined

    def test_ensure_interface_spec_constraints_extracts_query_params(self):
        """对话 URL 带查询串时，查询串单独作为文档化查询参数约束写入（差分探测依据）"""
        data = {"tool_id": "t", "parameters": [], "constraints": []}
        RequirementAnalyzer._ensure_interface_spec_constraints(data, self.CONVERSATION)
        joined = "\n".join(data["constraints"])
        # URL 契约仍是基础地址（逐字比对不受查询串影响）
        assert f"接口 URL: {DCD_URL}" in joined
        # 查询串原样保留 + 本地过滤规则提示
        assert "接口查询参数（用户 URL 原文查询串）: month=202608&rank_data_type=11&count=100&offset=0" in joined
        assert "本地过滤" in joined

    def test_ensure_query_params_idempotent(self):
        """查询串已在 constraints 中时不重复写入"""
        data = {
            "tool_id": "t",
            "parameters": [],
            "constraints": [
                "【接口规格】接口查询参数（用户 URL 原文查询串）: "
                "month=202608&rank_data_type=11&count=100&offset=0——仅这些参数名为接口真实查询参数",
            ],
        }
        RequirementAnalyzer._ensure_interface_spec_constraints(data, self.CONVERSATION)
        query_lines = [c for c in data["constraints"] if "接口查询参数" in c]
        assert len(query_lines) == 1

    def test_ensure_interface_spec_constraints_noop_when_present(self):
        """constraints 已含 URL 时不重复写入"""
        data = {
            "tool_id": "t",
            "parameters": [],
            "constraints": [f"接口地址 {DCD_URL} 原样调用"],
        }
        RequirementAnalyzer._ensure_interface_spec_constraints(data, self.CONVERSATION)
        url_lines = [c for c in data["constraints"] if DCD_URL in c]
        assert len(url_lines) == 1

    def test_ensure_interface_spec_constraints_no_url_noop(self):
        """对话无 URL 时不写任何约束"""
        data = {"tool_id": "t", "parameters": [], "constraints": []}
        RequirementAnalyzer._ensure_interface_spec_constraints(data, "本地股票数据需求，无外部接口")
        assert data["constraints"] == []

    def _spec_with_url_constraint(self) -> SkillSpec:
        return _make_spec([
            {"name": "month", "type": "string", "description": "月份", "required": True},
        ]).model_copy(
            update={"constraints": [f"【接口规格】接口 URL: {DCD_URL}，严禁改写"]}
        )

    def test_static_validator_catches_url_rewrite(self):
        """代码把 rank_data 写成 rank/data 时静态校验必须拦截"""
        spec = self._spec_with_url_constraint()
        code = GeneratedCode(
            code=(
                "def probe_tool(month: str = '202608'):\n"
                "    url = 'https://www.dongchedi.com/motor/pc/car/rank/data'\n"
                "    return {'status': 'success', 'data': []}\n"
            ),
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert not result.passed
        assert any("接口 URL 改写违规" in e and DCD_URL in e for e in result.errors)

    def test_static_validator_passes_verbatim_url(self):
        """URL 逐字使用时校验通过"""
        spec = self._spec_with_url_constraint()
        code = GeneratedCode(
            code=(
                f"API_URL = \"{DCD_URL}\"\n"
                "def probe_tool(month: str = '202608'):\n"
                "    return {'status': 'success', 'data': []}\n"
            ),
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert result.passed, f"应通过静态校验，错误: {result.errors}"

    def test_static_validator_catches_invented_endpoint(self):
        """代码臆造规格外的端点（如 brand/all 品牌解析）时静态校验必须拦截"""
        spec = self._spec_with_url_constraint()
        code = GeneratedCode(
            code=(
                f"API_URL = \"{DCD_URL}\"\n"
                "BRAND_URL = 'https://www.dongchedi.com/motor/pc/car/brand/all'\n"
                "def probe_tool(month: str = '202608'):\n"
                "    return {'status': 'success', 'data': []}\n"
            ),
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert not result.passed
        assert any("臆造接口端点违规" in e and "brand/all" in e for e in result.errors)

    def test_url_glued_to_chinese_text_not_polluted(self):
        """约束文本中 URL 后紧跟中文（如「rank_data」发起请求）时必须截断，不得误杀正确代码"""
        spec = _make_spec([
            {"name": "month", "type": "string", "description": "月份", "required": True},
        ]).model_copy(
            update={"constraints": [f"只能通过 {DCD_URL}」发起 GET 请求，请求头需包含 User-Agent"]}
        )
        code = GeneratedCode(
            code=(
                f"API_URL = \"{DCD_URL}\"\n"
                "def probe_tool(month: str = '202608'):\n"
                "    return {'status': 'success', 'data': []}\n"
            ),
            metadata={"tool_id": "probe_tool", "name": "probe", "description": "", "category": "market"},
            tests=[],
        )
        result = StaticValidator().validate(code, spec)
        assert result.passed, f"URL 正确却被拦截: {result.errors}"

    def test_conversation_url_glued_to_chinese_extracts_clean(self):
        """对话原文中 URL 后紧跟中文时，兜底提取出干净的 URL"""
        data = {"tool_id": "t", "parameters": [], "constraints": []}
        conversation = f"请直接请求{DCD_URL}发起GET调用，带 User-Agent"
        RequirementAnalyzer._ensure_interface_spec_constraints(data, conversation)
        joined = "\n".join(data["constraints"])
        assert DCD_URL in joined
        assert f"{DCD_URL}发起" not in joined

    def test_codegen_prompt_contains_interface_block(self):
        """user prompt 中含接口规格显著区块（含严禁改写提示）"""
        from core.tools.external.code_generator import CodeGenerator

        spec = self._spec_with_url_constraint()
        gen = CodeGenerator.__new__(CodeGenerator)
        prompt = gen._build_user_prompt(spec)
        assert "接口规格 — 唯一事实源" in prompt
        assert DCD_URL in prompt
        assert "严禁" in prompt
