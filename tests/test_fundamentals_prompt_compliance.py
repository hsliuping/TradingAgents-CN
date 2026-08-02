import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fundamentals_analyst_v2_templates_are_research_mode() -> None:
    templates_path = ROOT / "exports" / "current_db_templates.json"
    templates = json.loads(templates_path.read_text(encoding="utf-8"))

    target_templates = [
        item for item in templates
        if item.get("agent_name") == "fundamentals_analyst_v2"
        and item.get("template_name") in {
            "基本面分析师 v2.0 - 激进型",
            "基本面分析师 v2.0 - 中性型",
            "基本面分析师 v2.0 - 保守型",
        }
    ]

    assert len(target_templates) == 3

    required_phrases = [
        "核心观察",
        "财务与经营信号",
        "估值背景",
        "估值溢价",
        "总结",
        "get_financial_statements",
        "get_cash_flow_statement",
        "get_peer_comparison",
        "工具结果未提供",
        "报告期累计口径",
        "单季度推导",
        "行业特征",
        "不适用",
        "历史财务、历史估值区间和已披露经营数据",
        "当前股价、涨跌幅、成交量、当前总市值",
        "快照日期",
        "不得写成“截至分析日期”或用分析日期替代估值日期",
        "不能只改日期不解释原因",
        "核心观察` 第一条或 `## 估值背景` 开头",
        "当前尚无分析日对应的稳定收盘后日频数据，因此本次历史估值分位与同行估值按前一可用交易日口径分析",
        "不得直接结束报告",
    ]

    for template in target_templates:
        content = template["content"]
        combined_text = "\n".join(str(content.get(field, "")) for field in content)
        output_format = str(content.get("output_format", ""))
        user_prompt = str(content.get("user_prompt", ""))
        analysis_requirements = str(content.get("analysis_requirements", ""))

        assert "价格分析区间" not in output_format
        assert "合理价位区间" not in output_format
        assert "上涨空间" not in output_format
        assert "下行空间" not in output_format
        assert "仓位建议" not in output_format
        assert "风险敞口建议" not in output_format
        assert "建议" not in output_format

        assert "不得输出交易建议" in user_prompt
        assert "目标价" in user_prompt
        assert "不得使用 LLM 自身知识补数据" in user_prompt
        assert "不得把当前股价、当前总市值写进公司概况、核心观察或总结" in user_prompt
        assert "就必须同时注明该指标对应的快照日期" in user_prompt
        assert "不得写成“截至分析日期”或用分析日期替代估值日期" in user_prompt
        assert "不能只改日期不解释原因" in user_prompt
        assert "核心观察` 第一条或 `## 估值背景` 开头" in user_prompt
        assert "当前尚无分析日对应的稳定收盘后日频数据，因此本次历史估值分位与同行估值按前一可用交易日口径分析" in user_prompt
        assert "可以写：" in user_prompt
        assert "不得写：" in user_prompt
        assert "不必单列“待验证问题”" in user_prompt
        assert "不要求机械覆盖所有通用财务指标" in user_prompt
        assert "在生成正文前必须先拿到 get_stock_fundamentals_unified、get_financial_statements 和 get_cash_flow_statement 的结果" in user_prompt
        assert "Q2/Q3/Q4 不是单季度值" in combined_text
        assert (
            "优先使用这些字段分析季度变化" in combined_text
            or "优先使用该字段描述季度变化" in combined_text
        )
        assert "安全边际" in user_prompt
        assert "景气拐点" in user_prompt
        assert "不得输出" in analysis_requirements
        assert "交易动作" in analysis_requirements
        assert "表达方式示例" in analysis_requirements
        assert "不必单列“待验证问题”" in analysis_requirements
        assert "不要把其缺失直接写成风险或数据缺口" in analysis_requirements
        assert "必须先获得整体基本面、最近季度财报明细和最近季度现金流量表" in analysis_requirements
        assert "也不要把这些字段写进 `## 公司概况`、`## 核心观察`、`## 估值背景` 或 `## 总结`" in analysis_requirements
        assert "就必须同时注明该指标对应的快照日期" in analysis_requirements
        assert "不得写成“截至分析日期”或用分析日期替代估值日期" in analysis_requirements
        assert "不能只改日期不解释原因" in analysis_requirements
        assert "核心观察` 第一条或 `## 估值背景` 开头" in analysis_requirements
        assert "当前尚无分析日对应的稳定收盘后日频数据，因此本次历史估值分位与同行估值按前一可用交易日口径分析" in analysis_requirements
        assert (
            "不得把 Q1-Q4 直接相加" in analysis_requirements
            or "或把 Q1-Q4 直接相加" in analysis_requirements
        )
        assert "单季度推导" in combined_text
        assert "安全边际" in analysis_requirements
        assert "景气拐点" in analysis_requirements
        assert "禁止在报告中添加任何署名信息" in combined_text
        assert "禁止生成任何虚假的人名、作者信息或署名" in combined_text

        for phrase in required_phrases:
            assert phrase in combined_text


def test_fundamentals_analyst_v2_default_tools_include_peer_comparison() -> None:
    adapter_source = (ROOT / "core" / "agents" / "adapters" / "fundamentals_analyst_v2.py").read_text(encoding="utf-8")
    config_source = (ROOT / "core" / "agents" / "config.py").read_text(encoding="utf-8")

    assert "default_tools=[\"get_stock_fundamentals_unified\", \"get_financial_statements\", \"get_cash_flow_statement\", \"get_peer_comparison\"]" in adapter_source
    assert "max_tool_calls=4" in adapter_source
    # config.py 中保留较保守的默认工具列表，运行时以 adapter 文件中的 metadata 为准
    assert "fundamentals_analyst_v2" in config_source