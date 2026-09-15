# -*- coding: utf-8 -*-
"""外部接口预检（interface_preflight）单元测试。

验证：
- 从 spec.constraints 提取接口 URL 构造探测代码（含 URL、**kwargs 签名、请求头）
- 沙箱结果解读（verified / warning / failed）
"""

from core.tools.external.interface_preflight import (
    build_interface_probe,
    interpret_probe_result,
    _extract_query_params_from_parent_code,
)
from core.tools.external.skill_spec import SandboxResult, SkillSpec

DCD_URL = "https://www.dongchedi.com/motor/pc/car/rank_data"


def _make_spec(**overrides) -> SkillSpec:
    kwargs = dict(
        tool_id="dongchedi_probe",
        display_name="懂车帝探测",
        description="懂车帝车型月销量查询",
        category="market",
        data_source="dongchedi",
        parameters=[
            {"name": "month", "type": "string", "description": "月份", "required": True},
            {"name": "rank_data_type", "type": "int", "description": "榜单类型", "required": False, "default": 11},
        ],
        expected_output={"fields": ["rank", "car_model", "monthly_sales"]},
        constraints=[
            f"【接口规格 — 必须原样使用】接口 URL: {DCD_URL}（路径严禁改写）",
            "请求需携带 User-Agent 和 Referer 请求头",
        ],
        test_input={"month": "202608", "rank_data_type": 11},
    )
    kwargs.update(overrides)
    return SkillSpec(**kwargs)


class TestBuildInterfaceProbe:
    def test_probe_code_contains_url_and_headers(self):
        probe = build_interface_probe(_make_spec())
        assert probe is not None
        assert probe["url"] == DCD_URL
        assert DCD_URL in probe["code"]
        # 函数名与 tool_id 一致（沙箱 runner 按 tool_id 调用）
        assert "def dongchedi_probe(**kwargs)" in probe["code"]
        # 约束提到 Referer → 请求头带上
        assert "Referer" in probe["code"]
        assert "User-Agent" in probe["code"]
        # 请求参数来自 test_input
        assert probe["params"] == {"month": "202608", "rank_data_type": 11}

    def test_probe_uses_param_defaults_without_test_input(self):
        spec = _make_spec(test_input={})
        probe = build_interface_probe(spec)
        assert probe is not None
        assert probe["params"] == {"rank_data_type": 11}

    def test_no_url_constraints_returns_none(self):
        spec = _make_spec(constraints=["只能用本地数据"])
        assert build_interface_probe(spec) is None

    def test_domain_only_url_ignored(self):
        """纯域名（无路径）不作为接口地址"""
        spec = _make_spec(constraints=["参考 https://www.dongchedi.com/ 首页"])
        assert build_interface_probe(spec) is None

    def test_url_glued_chinese_truncated(self):
        """URL 后紧跟中文时截断（与校验器同一套 ASCII 正则）"""
        spec = _make_spec(constraints=[f"必须请求{DCD_URL}发起调用"])
        probe = build_interface_probe(spec)
        assert probe is not None
        assert probe["url"] == DCD_URL

    def test_documented_query_params_split_baseline_and_filters(self):
        """URL 带查询串时：文档化参数进基线，其余参数（如 brand_name）做差分测试"""
        spec = _make_spec(
            constraints=[
                "【接口规格 — 必须原样使用】接口 URL: "
                f"{DCD_URL}?month=202608&rank_data_type=11&count=100&offset=0（路径严禁改写）",
                "请求需携带 User-Agent 和 Referer 请求头",
            ],
            parameters=[
                {"name": "brand_name", "type": "string", "description": "品牌名", "required": True},
                {"name": "month", "type": "string", "description": "月份", "required": True},
            ],
            test_input={"brand_name": "比亚迪", "month": "202609"},
        )
        probe = build_interface_probe(spec)
        assert probe is not None
        # 基线 = 文档化查询参数 + test_input 对文档参数的覆盖（month 用新值）
        assert probe["baseline_params"] == {
            "month": "202609", "rank_data_type": "11", "count": "100", "offset": "0",
        }
        # brand_name 不在文档化查询参数中 → 疑似业务过滤参数
        assert probe["suspected_filters"] == ["brand_name"]
        # 传给沙箱的 test_input 保持原样（runner 按 tool_id 调用）
        assert probe["params"] == {"brand_name": "比亚迪", "month": "202609"}
        # 探测代码包含差分测试逻辑
        assert "ignored_params" in probe["code"]
        assert "filter_effective_params" in probe["code"]

    def test_documented_params_from_dedicated_constraint(self):
        """真实链路格式：URL 契约只含基础地址 + 专门的查询参数约束 → 差分仍触发。

        需求分析阶段 URL 契约约束剥掉查询串（防硬编码示例参数），
        查询串以「接口查询参数（用户 URL 原文查询串）」约束单列。
        """
        spec = _make_spec(
            constraints=[
                "【接口规格 — 必须原样使用】接口 URL: "
                f"{DCD_URL}（来自用户需求，路径/参数名严禁改写，如 rank_data 不得写成 rank/data）",
                "【接口规格】接口查询参数（用户 URL 原文查询串）: "
                "month=202608&rank_data_type=11&count=100&offset=0"
                "——仅这些参数名为接口真实查询参数，可拼装进 URL 请求；"
                "其余业务过滤条件必须拉取数据后按返回字段本地过滤",
                "请求需携带 User-Agent 和 Referer 请求头",
            ],
            parameters=[
                {"name": "brand_name", "type": "string", "description": "品牌名", "required": True},
                {"name": "month", "type": "string", "description": "月份", "required": True},
            ],
            test_input={"brand_name": "比亚迪", "month": "202609"},
        )
        probe = build_interface_probe(spec)
        assert probe is not None
        assert probe["url"] == DCD_URL
        assert probe["baseline_params"] == {
            "month": "202609", "rank_data_type": "11", "count": "100", "offset": "0",
        }
        assert probe["suspected_filters"] == ["brand_name"]

    def test_no_query_url_all_params_as_baseline(self):
        """URL 未带查询串：无从区分文档/业务参数，全部作为基线（不做差分）"""
        spec = _make_spec(
            parameters=[
                {"name": "brand_name", "type": "string", "description": "品牌名", "required": True},
                {"name": "month", "type": "string", "description": "月份", "required": True},
            ],
            test_input={"brand_name": "比亚迪", "month": "202608"},
        )
        probe = build_interface_probe(spec)
        assert probe is not None
        assert probe["baseline_params"] == {"brand_name": "比亚迪", "month": "202608"}
        assert probe["suspected_filters"] == []


class TestInterpretProbeResult:
    def _sandbox(self, output=None, success=True, error=None):
        return SandboxResult(success=success, error=error, output=output)

    def test_verified_with_data(self):
        result = interpret_probe_result(self._sandbox(output={
            "http_status": 200, "json_ok": True, "data_items": 100,
            "first_item_keys": ["rank", "series_name"],
        }))
        assert result["status"] == "verified"
        assert result["data_items"] == 100
        assert result["sample_fields"] == ["rank", "series_name"]

    def test_failed_on_404(self):
        result = interpret_probe_result(self._sandbox(output={"http_status": 404}))
        assert result["status"] == "failed"
        assert "404" in result["message"]

    def test_failed_on_network_error(self):
        result = interpret_probe_result(self._sandbox(output={
            "error": "ConnectionError: 连接超时"
        }))
        assert result["status"] == "failed"
        assert "不可达" in result["message"]

    def test_failed_on_sandbox_error(self):
        result = interpret_probe_result(self._sandbox(success=False, error="超时"))
        assert result["status"] == "failed"

    def test_warning_on_200_no_data(self):
        result = interpret_probe_result(self._sandbox(output={
            "http_status": 200, "json_ok": True,
        }))
        assert result["status"] == "warning"

    def test_warning_on_non_json(self):
        result = interpret_probe_result(self._sandbox(output={
            "http_status": 200, "json_ok": False, "body_head": "<html>",
        }))
        assert result["status"] == "warning"

    def test_ignored_params_reported_with_local_filter_hint(self):
        """差分测试：参数被接口忽略 → verdict 标记 ignored_params 并提示本地过滤"""
        result = interpret_probe_result(self._sandbox(output={
            "http_status": 200, "json_ok": True, "data_items": 100,
            "first_item_keys": ["rank", "series_name"],
            "ignored_params": ["brand_name"],
            "filter_test": {"tested": ["brand_name"], "baseline_items": 100,
                            "with_filter_items": 100, "with_filter_status": 200},
        }))
        assert result["status"] == "verified"
        assert result["ignored_params"] == ["brand_name"]
        assert "被接口忽略" in result["message"]
        assert "本地" in result["message"]

    def test_effective_filter_params_reported(self):
        """差分测试：参数改变返回 → verdict 标记 server_filter_params"""
        result = interpret_probe_result(self._sandbox(output={
            "http_status": 200, "json_ok": True, "data_items": 100,
            "first_item_keys": ["rank", "series_name"],
            "filter_effective_params": ["brand_name"],
        }))
        assert result["status"] == "verified"
        assert result["server_filter_params"] == ["brand_name"]
        assert "服务端过滤" in result["message"]

    def test_no_differential_output_unchanged(self):
        """无差分字段：verdict 不带 ignored_params / server_filter_params"""
        result = interpret_probe_result(self._sandbox(output={
            "http_status": 200, "json_ok": True, "data_items": 100,
            "first_item_keys": ["rank"],
        }))
        assert "ignored_params" not in result
        assert "server_filter_params" not in result


# ---------- 升级场景：父代码查询参数提取 ----------

_PARENT_CODE = '''
import requests

RANK_URL = "https://www.dongchedi.com/motor/pc/car/rank_data"


def _get_page(month, offset):
    params = {
        "month": month,
        "rank_data_type": "11",
        "count": "100",
        "offset": str(offset),
    }
    return requests.get(RANK_URL, params=params, timeout=10).json()
'''


class TestParentCodeParamExtraction:
    def test_extract_params_with_static_values(self):
        """AST 提取 params 键及静态值：字面量有值，运行期变量为 None（不猜默认）"""
        params = _extract_query_params_from_parent_code(_PARENT_CODE)
        assert list(params.keys()) == ["month", "rank_data_type", "count", "offset"]
        assert params["rank_data_type"] == "11"   # 字面量
        assert params["count"] == "100"           # 字面量
        assert params["month"] is None            # 函数入参，运行期未知
        assert params["offset"] is None           # str(入参)，运行期未知

    def test_only_params_flow_collected_not_other_dicts(self):
        """回归（真实缺陷）：只收集流入 requests(params=) 的字典。

        父代码里的请求头字典、品牌别名映射、输出结果字典与 params 字典
        同名键共存时，绝不能混进查询参数基线（曾把 User-Agent/Referer/
        别名/输出字段全混进预检基线）。
        """
        code = (
            "import requests\n"
            "URL = 'https://x.com/api'\n"
            "HEADERS = {'User-Agent': 'ua', 'Referer': 'https://x.com/'}\n"
            "ALIASES = {'aito问界': '问界', 'aito': '问界'}\n"
            "PAGE_SIZE = 100\n"
            "\n"
            "def fetch(month):\n"
            "    params = {'month': month, 'count': str(PAGE_SIZE), 'offset': '0'}\n"
            "    resp = requests.get(URL, params=params, headers=HEADERS)\n"
            "    result = {'month': month, 'offset': 0, 'pages_fetched': 1, 'fetch_mode': 'single_page'}\n"
            "    return result\n"
        )
        params = _extract_query_params_from_parent_code(code)
        # 只有真正传入 params= 的字典
        assert set(params.keys()) == {"month", "count", "offset"}
        assert params["count"] == "100"   # 常量追踪
        assert params["offset"] == "0"    # 字面量
        assert params["month"] is None    # 运行期变量
        # 头/别名/输出字典的键绝不出现
        assert "User-Agent" not in params
        assert "Referer" not in params
        assert "aito" not in params
        assert "fetch_mode" not in params
        assert "pages_fetched" not in params

    def test_constant_tracking(self):
        """模块常量（PAGE_SIZE = 100）追踪到 params 值"""
        code = (
            "import requests\n"
            "PAGE_SIZE = 100\n"
            "params = {'month': '202608', 'count': str(PAGE_SIZE)}\n"
            "requests.get('https://x.com/api', params=params)\n"
        )
        params = _extract_query_params_from_parent_code(code)
        assert params == {"month": "202608", "count": "100"}

    def test_inline_params_dict_supported(self):
        """内联 params={...} 写法也能提取键与字面量值"""
        code = (
            "import requests\n"
            "requests.get('https://x.com/api', params={'page': 1, 'size': 20})\n"
        )
        assert _extract_query_params_from_parent_code(code) == {"page": 1, "size": 20}

    def test_invalid_code_returns_empty(self):
        assert _extract_query_params_from_parent_code("def (") == {}

    def test_upgrade_baseline_uses_parent_static_values(self):
        """升级场景：基线用父代码静态值，新 spec 参数进差分，无静态值参数不硬编码。

        - month/rank_data_type：spec 有同名参数 → spec 值优先
        - count：父代码字面量 "100" → 进基线
        - offset：父代码是运行期变量且 spec 无同名参数 → 不发（不写死默认值）
        - brand/limit：不在父代码参数中 → 差分测试
        """
        spec = _make_spec(
            parameters=[
                {"name": "month", "type": "string", "description": "月份", "required": True},
                {"name": "rank_data_type", "type": "string", "description": "榜单类型", "required": False},
                {"name": "brand", "type": "string", "description": "品牌", "required": False},
                {"name": "limit", "type": "integer", "description": "条数上限", "required": False},
            ],
            test_input={"month": "202608", "rank_data_type": "sale", "brand": "比亚迪", "limit": 10},
        )
        probe = build_interface_probe(spec, parent_code=_PARENT_CODE)
        assert probe is not None
        assert probe["baseline_params"]["month"] == "202608"
        assert probe["baseline_params"]["rank_data_type"] == "sale"
        assert probe["baseline_params"]["count"] == "100"
        # 求不出静态值 → 不写死默认、不发该参数
        assert "offset" not in probe["baseline_params"]
        # 新 spec 的业务参数做差分（不再被当成接口可用参数）
        assert set(probe["suspected_filters"]) == {"brand", "limit"}

    def test_without_parent_code_no_diff_when_bare_url(self):
        """回归：无父代码且约束无查询串时，全部参数作基线（不做差分）"""
        spec = _make_spec(
            parameters=[{"name": "brand", "type": "string", "description": "品牌", "required": False}],
            test_input={"brand": "比亚迪"},
        )
        probe = build_interface_probe(spec)
        assert probe is not None
        assert probe["suspected_filters"] == []
