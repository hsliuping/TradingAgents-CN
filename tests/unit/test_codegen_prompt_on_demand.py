# -*- coding: utf-8 -*-
"""CodeGenerator system prompt 按需注入测试。

验证需求类型分流（external_api / local_data）对 system prompt 的裁剪：
- external_api（外部接口集成，如懂车帝）：不注入本地股票数据资产文档
- local_data（默认）：用紧凑 API 索引替代全量 API 文档
"""

import pytest

from core.tools.external.code_generator import (
    CODING_PATTERNS,
    EXTERNAL_API_RULES,
    LOCAL_DATA_API_INDEX,
    PROJECT_ACCESS_INDEX,
    CodeGenerator,
)
from core.tools.external.iteration_controller import IterationController
from core.tools.external.requirement_analyzer import classify_requirement_mode
from core.tools.external.skill_spec import SkillSpec


def _make_spec(**overrides) -> SkillSpec:
    kwargs = dict(
        tool_id="probe_test",
        display_name="探针测试",
        description="查询某只A股近5年的营业收入和净利润趋势",
        category="fundamentals",
        data_source="tushare",
        parameters=[{"name": "symbol", "type": "string", "description": "股票代码", "required": True}],
        expected_output={"fields": ["symbol", "years", "revenue"]},
    )
    kwargs.update(overrides)
    return SkillSpec(**kwargs)


@pytest.fixture()
def generator() -> CodeGenerator:
    return CodeGenerator()


# ---------- external_api 模式 ----------

class TestExternalApiPrompt:
    def test_dongchedi_spec_classified_as_external_api(self):
        spec = _make_spec(
            tool_id="dongchedi_manufacturer_model_monthly_sales",
            display_name="懂车帝厂商车型月度销量",
            description="从懂车帝接口获取指定厂商的车型月度销量数据",
            data_source="dongchedi",
            category="market",
        )
        assert classify_requirement_mode(spec) == "external_api"

    def test_external_api_prompt_excludes_local_assets(self, generator):
        """外部接口需求：不应注入本地股票数据资产文档"""
        spec = _make_spec(data_source="dongchedi")
        prompt = generator._build_system_prompt(spec)

        # 本地资产内容一律不注入
        assert "本地数据访问 — API 索引" not in prompt
        assert "项目数据访问 — API 索引" not in prompt
        assert "股票数据集合" not in prompt
        assert "数据契约" not in prompt
        assert "参考模板" not in prompt
        assert "允许导入以下模块" not in prompt
        assert "Helper 透传铁律" not in prompt
        assert "get_stock_basic_info" not in prompt

        # 外部接口规则与输出格式必须保留
        assert "外部接口集成关键要求" in prompt
        assert EXTERNAL_API_RULES.strip().splitlines()[1] in prompt
        assert "=== CODE START ===" in prompt
        assert "=== TESTS END ===" in prompt
        # 编码规范保留（通用铁律）
        assert CODING_PATTERNS[:20] in prompt

    def test_external_api_prompt_much_smaller(self, generator):
        """外部接口 prompt 应显著小于本地数据 prompt"""
        ext_prompt = generator._build_system_prompt(_make_spec(data_source="dongchedi"))
        local_prompt = generator._build_system_prompt(_make_spec())
        assert len(ext_prompt) < len(local_prompt) * 0.5

    def test_out_of_catalog_source_drops_catalog_doc(self, generator):
        """目录外数据源（dongchedi）：不注入 AKShare/Tushare 目录详情，改为目录外集成说明"""
        prompt = generator._build_system_prompt(_make_spec(data_source="dongchedi"))

        assert "目录外接口集成" in prompt
        assert "唯一事实源" in prompt
        # 目录详情条目不注入（避免诱导 LLM 改用 AKShare/Tushare）
        assert "AKShareProvider" not in prompt
        assert "TushareProvider" not in prompt
        assert "get_akshare_provider" not in prompt

    def test_external_api_user_prompt_skips_factor_catalog(self, generator):
        """外部接口需求：user prompt 不注入股票因子白名单（MA/RSI/MACD 等无关内容）"""
        spec = _make_spec(
            tool_id="dongchedi_car_rank_data",
            display_name="懂车帝车型月销量查询",
            description="通过懂车帝PC端车型销量排行接口，按指定月份或聚合周期获取全国车型月度销量数据",
            data_source="dongchedi",
            category="market",
            expected_output={"fields": ["rank", "car_model", "monthly_sales"]},
        )
        prompt = generator._build_user_prompt(spec)

        assert "常用分析因子白名单" not in prompt
        assert "technical_core" not in prompt
        assert "MACD" not in prompt
        assert "KDJ" not in prompt
        # 本地运行时接口约束不注入
        assert "Skill Runtime 接口约束" not in prompt
        assert "core.skill_runtime.data_access" not in prompt
        # 「改用 akshare/tushare 替代」会诱导抛弃用户指定接口，替换为外部接口版本
        assert "改用 akshare、tushare 等免费替代方案" not in prompt
        assert "不得改用其他数据源" in prompt
        # 严禁模拟约束保留
        assert "严禁模拟/占位" in prompt

    def test_local_user_prompt_keeps_runtime_and_factor_sections(self, generator):
        """本地数据需求：保留运行时接口约束与因子约束区块"""
        prompt = generator._build_user_prompt(_make_spec())
        assert "Skill Runtime 接口约束" in prompt
        assert "常用分析因子约束" in prompt


# ---------- local_data 模式 ----------

class TestLocalDataPrompt:
    def test_local_data_spec_classified_as_local(self):
        assert classify_requirement_mode(_make_spec()) == "local_data"

    def test_local_prompt_uses_compact_index(self, generator):
        """本地数据需求：紧凑索引替代全量 API 文档"""
        prompt = generator._build_system_prompt(_make_spec())

        assert "本地数据访问 — API 索引" in prompt
        assert "项目数据访问 — API 索引" in prompt
        assert "get_stock_valuation_context" in prompt
        assert "get_external_valuation_data" in prompt
        # 核心防幻觉规则保留
        assert "Helper 透传铁律" in prompt
        assert "防御性编程" in prompt

    def test_local_prompt_smaller_than_full_docs(self, generator):
        """紧凑索引版本应明显小于旧全量文档版本"""
        from core.skill_runtime.data_access import LOCAL_DATA_API_DOC
        from core.skill_runtime.project_access import PROJECT_DATA_ACCESS_DOC

        prompt = generator._build_system_prompt(_make_spec())
        # 还原旧版（全量文档替代索引）的等效大小做对比
        old_equivalent = (
            len(prompt)
            + len(LOCAL_DATA_API_DOC) + len(PROJECT_DATA_ACCESS_DOC)
            - len(LOCAL_DATA_API_INDEX) - len(PROJECT_ACCESS_INDEX)
        )
        assert len(prompt) < old_equivalent - 4000

    def test_index_constants_are_compact(self):
        """索引常量本身保持紧凑（显著小于对应全量文档）"""
        from core.skill_runtime.data_access import LOCAL_DATA_API_DOC
        from core.skill_runtime.project_access import PROJECT_DATA_ACCESS_DOC

        assert len(LOCAL_DATA_API_INDEX) < len(LOCAL_DATA_API_DOC) * 0.5
        assert len(PROJECT_ACCESS_INDEX) < len(PROJECT_DATA_ACCESS_DOC) * 0.5


# ---------- Agent Loop 协调者 prompt 分流 ----------

class TestAgenticSystemPrompt:
    def test_external_api_prompt_drops_stock_assumptions(self):
        """外部接口需求：Agent Loop prompt 不应包含股票预检/helper 复用等本地假设"""
        spec = _make_spec(data_source="dongchedi")
        prompt = IterationController._build_agentic_system_prompt(spec)

        assert "外部接口集成" in prompt
        # 本地数据假设一律剔除
        assert "get_stock_basic_info" not in prompt
        assert "数据源标签使用规则" not in prompt
        assert "必须复用已有工具" not in prompt
        assert "list_analysis_tools" not in prompt
        assert "股票代码预检" not in prompt
        # 外部接口防御规则保留
        assert "参数防御" in prompt
        assert "timeout=10" in prompt
        assert "pipeline_tool" in prompt

    def test_local_data_prompt_keeps_stock_rules(self):
        """本地数据需求：Agent Loop prompt 保留股票预检/helper 复用规则"""
        prompt = IterationController._build_agentic_system_prompt(_make_spec())
        assert "get_stock_basic_info" in prompt
        assert "数据源标签使用规则" in prompt
        assert "必须复用已有工具" in prompt
        assert "list_analysis_tools" in prompt
        assert "股票代码预检" in prompt

    def test_no_spec_defaults_to_local(self):
        """未传 spec 时默认 local_data 分支（向后兼容）"""
        prompt = IterationController._build_agentic_system_prompt(None)
        assert "get_stock_basic_info" in prompt


# ---------- 接口预检实测事实注入（spec.metadata.interface_preflight → user prompt） ----------

_VERIFIED_PREFLIGHT = {
    "status": "verified",
    "http_status": 200,
    "data_items": 10,
    "sample_fields": ["series_id", "series_name", "rank", "min_price", "max_price"],
    # 基线查询参数（文档化）；brand_name 经差分测试被判定为被接口忽略
    "probed_params": {"month": "202608", "rank_data_type": 11, "count": 100, "offset": 0},
    "ignored_params": ["brand_name"],
    "url": "https://www.dongchedi.com/motor/pc/car/rank_data",
    "checked_at": "2026-09-15T10:00:00",
}


class TestPreflightFactsBlock:
    def _preflight_spec(self, preflight) -> SkillSpec:
        return _make_spec(
            tool_id="dongchedi_car_rank_data",
            display_name="懂车帝车型月销量查询",
            description="通过懂车帝PC端车型销量排行接口，按指定月份或聚合周期获取全国车型月度销量数据",
            data_source="dongchedi",
            category="market",
            metadata={"interface_preflight": preflight},
        )

    def test_verified_preflight_injects_real_fields_and_params(self, generator):
        """verified 预检：实测 URL/真实字段/基线参数全部注入区块"""
        block = generator._build_preflight_facts_block(self._preflight_spec(_VERIFIED_PREFLIGHT))

        assert "接口实测事实" in block
        assert "https://www.dongchedi.com/motor/pc/car/rank_data" in block
        assert "series_name" in block and "min_price" in block
        assert "month='202608'" in block
        assert "返回数据条数: 10" in block
        # brand_name 是被忽略参数，不在实测可用查询参数中
        assert "brand_name" not in block.split("实测验证可用的查询参数")[1].split("\n")[0]

    def test_verified_block_contains_local_filter_rule(self, generator):
        """核心规则：业务过滤参数不在实测查询参数中 → 不得拼 URL，拉全量后本地过滤"""
        block = generator._build_preflight_facts_block(self._preflight_spec(_VERIFIED_PREFLIGHT))

        assert "brand" in block
        assert "拼进 URL" in block
        assert "本地实现" in block
        # 严禁臆造字段规则
        assert "严禁臆造字段名" in block

    def test_ignored_params_get_dedicated_rule(self, generator):
        """差分测试产出 ignored_params → 专属规则点名该参数"""
        block = generator._build_preflight_facts_block(self._preflight_spec(_VERIFIED_PREFLIGHT))

        assert "被接口忽略" in block
        assert "brand_name" in block
        # 点名规则 + 本地过滤指示
        assert "严禁拼进 URL" in block
        assert "series_name" in block  # 品牌匹配用返回字段

    def test_server_filter_params_allowed_in_url(self, generator):
        """差分测试产出 server_filter_params → 提示可作 URL 查询参数"""
        preflight = dict(_VERIFIED_PREFLIGHT)
        preflight.pop("ignored_params")
        preflight["server_filter_params"] = ["brand_name"]
        block = generator._build_preflight_facts_block(self._preflight_spec(preflight))

        assert "服务端过滤疑似生效" in block
        assert "可作 URL 查询参数" in block
        # 无 ignored_params 时用通用规则（仍禁止臆造其他过滤参数）
        assert "臆造为接口查询参数" in block

    def test_ignored_param_without_matching_field_gets_boundary_rule(self, generator):
        """被忽略参数在返回字段中无对应字段 → 注入数据边界规则（数据驱动，非关键词写死）。

        brand_name 被实测忽略，sample_fields 里没有任何名称相关的字段 → 边界规则。
        """
        block = generator._build_preflight_facts_block(self._preflight_spec(_VERIFIED_PREFLIGHT))

        assert "不存在与 brand_name 对应的字段" in block
        assert "结果可能不完整" in block
        assert "严禁臆造新接口端点" in block

    def test_ignored_param_with_matching_field_no_boundary_rule(self, generator):
        """被忽略参数在返回字段中有对应字段（brand_name ↔ brand_name）→ 无边界规则"""
        preflight = dict(_VERIFIED_PREFLIGHT)
        preflight["sample_fields"] = ["series_id", "series_name", "brand_name", "rank"]
        block = generator._build_preflight_facts_block(self._preflight_spec(preflight))

        assert "不存在与" not in block

    def test_boundary_rule_data_driven_any_filter(self, generator):
        """边界规则与业务域无关：换一个被忽略参数（city）同样成立"""
        preflight = dict(_VERIFIED_PREFLIGHT)
        preflight["ignored_params"] = ["city"]
        block = generator._build_preflight_facts_block(self._preflight_spec(preflight))

        assert "不存在与 city 对应的字段" in block

    def test_warning_preflight_uses_structural_caution(self, generator):
        """warning 预检（接口可达但结构未探明）：注入结构探测告诫而非字段清单"""
        preflight = {
            "status": "warning",
            "http_status": 200,
            "message": "接口可达（HTTP 200，JSON 响应），但未识别到数据条目",
            "url": "https://example.com/api/data",
        }
        block = generator._build_preflight_facts_block(self._preflight_spec(preflight))

        assert "未识别到数据条目" in block
        assert "JSON 顶层键" in block
        assert "本地" in block  # 过滤仍需本地实现

    def test_no_preflight_no_block(self, generator):
        """无预检结果（local_data / 未跑预检）：不注入区块"""
        assert generator._build_preflight_facts_block(_make_spec()) == ""
        assert generator._build_preflight_facts_block(
            self._preflight_spec({"status": "verified"})  # 无 url 视为无效
        ) == ""

    def test_user_prompt_includes_preflight_block(self, generator):
        """集成：user prompt 中出现实测事实区块与真实字段"""
        prompt = generator._build_user_prompt(self._preflight_spec(_VERIFIED_PREFLIGHT))

        assert "接口实测事实" in prompt
        assert "series_name" in prompt
        # 无预检时不出现在 prompt 中
        plain_prompt = generator._build_user_prompt(
            _make_spec(data_source="dongchedi")
        )
        assert "接口实测事实" not in plain_prompt

    def test_agentic_task_prompt_includes_preflight_block(self):
        """Agent Loop 协调者任务 prompt 也注入实测事实区块（反馈指导不跑偏）"""
        prompt = IterationController._build_agentic_task_prompt(
            self._preflight_spec(_VERIFIED_PREFLIGHT), "", None
        )

        assert "接口实测事实" in prompt
        assert "被接口忽略" in prompt
        assert "brand_name" in prompt
        assert "本地实现" in prompt
        # 无预检时无区块
        plain = IterationController._build_agentic_task_prompt(
            _make_spec(data_source="dongchedi"), "", None
        )
        assert "接口实测事实" not in plain


# ---------- 版本升级：父代码基线 + 最小改动指令 ----------

_PARENT_CODE = '''"""父版本：懂车帝车型销量查询（已通过验证）"""
import requests

RANK_URL = "https://www.dongchedi.com/motor/pc/car/rank_data"


def parent_tool(brand: str = "比亚迪", month: str = "202608"):
    params = {"month": month, "rank_data_type": "11", "count": "100", "offset": "0"}
    resp = requests.get(RANK_URL, params=params, timeout=10)
    records = resp.json().get("data", {}).get("list", [])
    matched = [r for r in records if brand in (r.get("series_name") or "")]
    return {"status": "success", "data": matched}
'''


class TestUpgradeModePrompt:
    def test_upgrade_block_with_parent_code_and_no_feedback(self, generator):
        """升级模式：有父代码、无失败反馈 → 升级区块而非修复区块"""
        prompt = generator._build_user_prompt(
            _make_spec(tool_id="parent_tool_v2"),
            feedback="",
            previous_code=_PARENT_CODE,
            iteration_mode="upgrade",
        )

        assert "版本升级" in prompt
        assert "做最小改动" in prompt
        assert "严禁从零重写" in prompt
        # 父代码作为基线展示
        assert "当前版本代码（已通过验证，是本次升级的基线）" in prompt
        assert "rank_data" in prompt
        # 不能误用修复区块文案
        assert "迭代修复" not in prompt

    def test_upgrade_block_rules_cover_minimal_change(self, generator):
        """升级区块包含保留已验证逻辑/不重新设计/函数名以新规格为准等规则"""
        prompt = generator._build_user_prompt(
            _make_spec(tool_id="parent_tool_v2"),
            feedback="新增一个 price_level 字段",
            previous_code=_PARENT_CODE,
            iteration_mode="upgrade",
        )

        assert "保留已验证逻辑" in prompt
        assert "不重新设计" in prompt
        assert "函数名以新规格为准" in prompt
        assert "parent_tool_v2" in prompt  # 新规格函数名出现在 spec JSON 中
        # 升级需求文本也注入
        assert "price_level" in prompt

    def test_repair_mode_keeps_original_fix_block(self, generator):
        """回归：repair 模式仍是定向修复区块"""
        prompt = generator._build_user_prompt(
            _make_spec(),
            feedback="沙箱执行 404：URL 被改写",
            previous_code=_PARENT_CODE,
            iteration_mode="repair",
        )

        assert "迭代修复" in prompt
        assert "定向修复" in prompt
        assert "版本升级" not in prompt

    def test_no_previous_code_no_iteration_block(self, generator):
        """回归：无父代码/无上轮代码时不出现任何迭代区块"""
        prompt = generator._build_user_prompt(
            _make_spec(), feedback="", previous_code="", iteration_mode="upgrade"
        )

        assert "版本升级" not in prompt
        assert "迭代修复" not in prompt

    def test_agentic_task_prompt_upgrade_carries_parent_code(self):
        """协调者任务 prompt：升级时带父代码基线与最小改动规划要求"""
        prompt = IterationController._build_agentic_task_prompt(
            _make_spec(tool_id="parent_tool_v2"),
            "",
            None,
            parent_code=_PARENT_CODE,
        )

        assert "版本升级任务" in prompt
        assert "不是从零生成" in prompt
        assert "rank_data" in prompt
        # 协调者被要求只规划差异点改动
        assert "差异点" in prompt and "保留" in prompt

    def test_agentic_task_prompt_without_parent_code_no_upgrade_block(self):
        """回归：非升级场景协调者 prompt 不含升级区块"""
        prompt = IterationController._build_agentic_task_prompt(
            _make_spec(), "", None
        )
        assert "版本升级任务" not in prompt
