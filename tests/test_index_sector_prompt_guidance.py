import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, module_name: str):
    module_path = ROOT / relative_path
    module_spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def test_research_brief_index_and_sector_builders_keep_explicit_tool_workflow() -> None:
    module = _load_module(
        "scripts/template_upgrades/update_research_brief_v2_prompts.py",
        "update_research_brief_v2_prompts",
    )

    index_content = module.build_index_analyst_content("neutral")
    sector_content = module.build_sector_analyst_content("neutral")

    assert "get_market_overview" in index_content["tool_guidance"]
    assert "get_china_market_overview" in index_content["tool_guidance"]
    assert "get_index_data" in index_content["tool_guidance"]
    assert "必须使用上述参数值" in index_content["tool_guidance"]
    assert "不要使用其他日期" in index_content["tool_guidance"]
    assert "研究口径" in index_content["system_prompt"]
    assert "研究口径" in index_content["user_prompt"]
    assert "中性视角解释市场状态" in index_content["user_prompt"]
    assert "趋势、资金、情绪、周期和正反证据的事实平衡" in index_content["user_prompt"]
    assert "数据冲突、异常、缺失或证据不足" in index_content["analysis_requirements"]
    assert "不要单独设“数据缺口声明”章节" in index_content["analysis_requirements"]
    assert "证据不足，只能降低结论强度" in index_content["analysis_requirements"]
    assert "市场周期与正反证据评估只引用工具直接返回和可回溯指标" in index_content["analysis_requirements"]
    assert "两融变化字段与当前余额明显不匹配" in index_content["analysis_requirements"]
    assert "只能留在数据说明中" in index_content["analysis_requirements"]
    assert "不得外推为“均线下行态势”" in index_content["analysis_requirements"]
    assert "技术标签或规则识别区间都只是规则描述，不等同于市场结论" in index_content["analysis_requirements"]
    assert "成交额、换手率、涨跌家数等事实指标由模型自行归纳" in index_content["analysis_requirements"]
    assert "允许写法示例" in index_content["analysis_requirements"]
    assert "过线写法示例" in index_content["analysis_requirements"]
    assert "短期数据表现偏强" in index_content["analysis_requirements"]
    assert "情绪修复完成" in index_content["analysis_requirements"]
    assert "总成交额为 23246.35 亿元，上海/深圳市场成交额占比分别为 41.2% 和 58.8%" in index_content["analysis_requirements"]
    assert "两融数据若不完整，应明确说明不纳入资金面综合评估" in index_content["analysis_requirements"]
    assert "技术指标整体偏多，但高位指标提示短期仍需关注波动" in index_content["analysis_requirements"]
    assert "涨跌停明细名单显示涨停 59 家、跌停 8 家，连板 17 家" in index_content["analysis_requirements"]
    assert "成交活跃度显著提升" in index_content["analysis_requirements"]
    assert "无法确认杠杆资金态度" in index_content["analysis_requirements"]
    assert "三个指标均显示看多信号" in index_content["analysis_requirements"]
    assert "融资余额处于谨慎水平" in index_content["analysis_requirements"]
    assert "涨停 81 家（其中涨停家数 59 家）" in index_content["analysis_requirements"]
    assert "不要使用“空间”“站稳”“突破”" in index_content["analysis_requirements"]
    assert "不要写 PE/PB、股息率、估值分位" in index_content["analysis_requirements"]
    assert "只能作为数据说明" in index_content["user_prompt"]
    assert "不要自行延伸成均线斜率、风格切换或高位调整叙事" in index_content["user_prompt"]
    assert "工具返回的技术标签或规则区间只可作为描述线索，不要直接改写成市场定性结论" in index_content["user_prompt"]
    assert "用‘短期数据表现偏强’替代‘情绪修复完成’" in index_content["user_prompt"]
    assert "用‘总成交额、平均每家上市公司成交额和换手率的事实数据’替代‘成交活跃度显著提升’" in index_content["user_prompt"]
    assert "用‘无法确认杠杆资金方向’替代‘无法确认杠杆资金态度’" in index_content["user_prompt"]
    assert "用‘技术指标整体偏多’替代‘三个指标均显示看多信号’" in index_content["user_prompt"]
    assert "两融完整时只引用余额与变化数值；若数据不完整，直接说明不纳入综合评估" in index_content["user_prompt"]
    assert "涨跌停家数统一采用涨跌停明细名单口径，不要混用 `pct_chg` 阈值近似结果" in index_content["user_prompt"]
    assert "数据缺口声明" not in index_content["system_prompt"]
    assert "PE、PB" not in index_content["system_prompt"]
    assert "数据缺口声明" not in index_content["user_prompt"]
    assert "PE/PB" not in index_content["user_prompt"]
    assert "实际数据日期" not in index_content["system_prompt"]

    assert "get_sector_data" in sector_content["tool_guidance"]
    assert "get_peer_comparison" in sector_content["tool_guidance"]
    assert "get_fund_flow_data" in sector_content["tool_guidance"]
    assert "必须使用上述参数值" in sector_content["tool_guidance"]
    assert "不要使用其他股票代码或日期" in sector_content["tool_guidance"]
    assert "研究口径" in sector_content["system_prompt"]
    assert "坚持研究口径" in sector_content["system_prompt"]
    assert "趋势判断要说明原因" in sector_content["system_prompt"]
    assert "异常字段不得进入综合判断" in sector_content["system_prompt"]
    assert "行业标签必须分层处理" in sector_content["system_prompt"]
    assert "唯一锚点" in sector_content["system_prompt"]
    assert "股票基础行业字段（单值 industry）" in sector_content["system_prompt"]
    assert "有限行业常识只能作背景说明" in sector_content["system_prompt"]
    assert "更贴近主业的细分行业标签" in sector_content["tool_guidance"]
    assert "唯一主行业锚点" in sector_content["tool_guidance"]
    assert "如果引用少量行业通识" in sector_content["tool_guidance"]
    assert "主力资金显著配置" in sector_content["tool_guidance"]
    assert "个股资金流回退数据" in sector_content["tool_guidance"]
    assert "研究口径" in sector_content["user_prompt"]
    assert "唯一主行业锚点" in sector_content["user_prompt"]
    assert "允许少量行业通识作为背景说明" in sector_content["user_prompt"]
    assert "更贴近主业的行业口径" in sector_content["user_prompt"]
    assert "未进入当日行业资金净流入前列" in sector_content["user_prompt"]
    assert "个股资金流回退数据" in sector_content["user_prompt"]
    assert "未进入当日个股资金净流入前列" in sector_content["user_prompt"]
    assert "利率、监管、资产质量、息差、不良率、拨备覆盖率" in sector_content["user_prompt"]
    assert "安全边际、修复窗口或板块机会叙事" in sector_content["user_prompt"]
    assert "成熟阶段、增长空间有限" in sector_content["user_prompt"]
    assert "资产质量担忧/息差收窄压力" in sector_content["user_prompt"]
    assert "资金流向与市场热度" in sector_content["analysis_requirements"]
    assert "风险与结构性特征的事实型平衡评估" in sector_content["analysis_requirements"]
    assert "趋势、景气、竞争、轮动、估值分化和资金流向判断" in sector_content["analysis_requirements"]
    assert "不要单独设“数据缺口声明”章节" in sector_content["analysis_requirements"]
    assert "对所有 A 股个股，正文只能保留一个主行业归属" in sector_content["analysis_requirements"]
    assert "如果同一股票命中多个行业类指数" in sector_content["analysis_requirements"]
    assert "银行个股同时命中“金融(A股)”" in sector_content["analysis_requirements"]
    assert "允许少量行业通识作为背景说明" in sector_content["analysis_requirements"]
    assert "未进入当日行业资金净流入前列" in sector_content["analysis_requirements"]
    assert "个股资金流回退数据" in sector_content["analysis_requirements"]
    assert "安全边际" in sector_content["analysis_requirements"]
    assert "成熟发展阶段，行业增长空间有限" in sector_content["analysis_requirements"]
    assert "资产质量担忧和息差收窄压力" in sector_content["analysis_requirements"]
    assert "行业机会与风险" not in sector_content["user_prompt"]


def test_research_mode_migration_preserves_index_and_sector_tool_instructions() -> None:
    module = _load_module(
        "scripts/compliance/migrate_prompt_templates_to_research_mode.py",
        "migrate_prompt_templates_to_research_mode",
    )

    index_guidance = module.get_field_override("index_analyst", "tool_guidance")
    sector_guidance = module.get_field_override("sector_analyst", "tool_guidance")
    index_system_prompt = module.get_field_override("index_analyst", "system_prompt")
    sector_system_prompt = module.get_field_override("sector_analyst", "system_prompt")

    assert index_guidance is not None
    assert sector_guidance is not None
    assert index_system_prompt is not None
    assert sector_system_prompt is not None

    assert "get_market_overview" in index_guidance
    assert "get_index_data" in index_guidance
    assert "必须先调用工具获取数据" in index_guidance
    assert "研究口径" in index_system_prompt
    assert "坚持研究口径" in index_system_prompt
    assert "判断原因" in index_system_prompt
    assert "数据缺口声明" not in index_system_prompt
    assert "PE、PB" not in index_system_prompt
    assert "PE/PB" not in index_guidance
    index_requirements = module.get_field_override("index_analyst", "analysis_requirements")
    assert index_requirements is not None
    assert "大盘趋势和技术形态" in index_requirements
    assert "资金流向（北向、两融）" in index_requirements
    assert "趋势判断必须同时说明对应的数据依据和形成原因" in index_requirements
    assert "数据冲突、异常、缺失或证据不足" in index_requirements
    assert "不要单独设“数据缺口声明”章节" in index_requirements
    assert "市场周期与正反证据评估只引用工具直接返回和可回溯指标" in index_requirements
    assert "两融变化字段与当前余额明显不匹配" in index_requirements
    assert "只能留在数据说明中" in index_requirements
    assert "不得外推为“均线下行态势”" in index_requirements
    assert "技术标签或规则识别区间都只是规则描述，不等同于市场结论" in index_requirements
    assert "成交额、换手率、涨跌家数等事实指标由模型自行归纳" in index_requirements
    assert "允许写法示例" in index_requirements
    assert "过线写法示例" in index_requirements
    assert "总成交额为 23246.35 亿元，上海/深圳市场成交额占比分别为 41.2% 和 58.8%" in index_requirements
    assert "两融数据若不完整，应明确说明不纳入资金面综合评估" in index_requirements
    assert "技术指标整体偏多，但高位指标提示短期仍需关注波动" in index_requirements
    assert "涨跌停明细名单显示涨停 59 家、跌停 8 家，连板 17 家" in index_requirements
    assert "不要使用“空间”“站稳”“突破”" in index_requirements
    assert "不要写 PE/PB、股息率、估值分位" in index_requirements

    assert "get_sector_data" in sector_guidance
    assert "get_peer_comparison" in sector_guidance
    assert "必须先调用工具获取数据" in sector_guidance
    assert "唯一主行业锚点" in sector_guidance
    assert "研究口径" in sector_system_prompt
    assert "判断原因" in sector_system_prompt
    assert "层级标签" in sector_system_prompt
    assert "股票基础行业字段（单值 industry）" in sector_system_prompt
    assert "允许少量行业通识作为背景说明" in sector_system_prompt
    assert "实际数据日期" not in sector_system_prompt
    assert "个股资金流回退数据" in sector_guidance
    assert "如果引用少量行业通识" in sector_guidance
    sector_requirements = module.get_field_override("sector_analyst", "analysis_requirements")
    assert sector_requirements is not None
    assert "资金流向与市场热度" in sector_requirements
    assert "事实型平衡评估" in sector_requirements
    assert "趋势、景气、竞争、轮动、估值分化和资金流向判断" in sector_requirements
    assert "不要单独设“数据缺口声明”章节" in sector_requirements
    assert "对所有 A 股个股，正文只能保留一个主行业归属" in sector_requirements
    assert "如果同一股票命中多个行业类指数" in sector_requirements
    assert "更贴近主业的行业口径" in sector_requirements
    assert "允许少量行业通识作为背景说明" in sector_requirements
    assert "未进入当日行业资金净流入前列" in sector_requirements
    assert "未进入当日个股资金净流入前列" in sector_requirements


def test_runtime_analyst_prompt_avoids_missing_dimension_sections() -> None:
    source = (ROOT / "core/agents/analyst.py").read_text(encoding="utf-8")

    assert "不要单独列出“未获取的数据维度”" in source
    assert "本报告未获取以下维度数据，不作相关分析" in source
    assert "KOL 观点、散户情绪、机构持仓、行业资金流向" in source
    assert "如果工具返回“汇总口径/明细口径”" in source
    assert "必须同时保留两套数值，并明确写出“存在口径差异”" in source
    assert "该维度数据缺失，暂不分析" not in source


def test_index_fallback_prompts_drop_information_gap_wording() -> None:
    source = (ROOT / "core/agents/adapters/index_analyst_v2.py").read_text(encoding="utf-8")

    assert "关键观察信号与后续验证事项" in source
    assert "关键宏观信号与后续观察事项" in source
    assert "5. 关键观察信号、信息缺口与后续验证事项" not in source
    assert "3. 关键宏观信号、信息缺口与后续观察事项" not in source


def test_sector_fallback_prompt_limits_background_industry_inference() -> None:
    source = (ROOT / "core/agents/adapters/sector_analyst_v2.py").read_text(encoding="utf-8")

    assert "允许少量行业通识作为背景说明" in source
    assert "显式标注为背景" in source
    assert "行业处于成熟阶段、增长空间有限" in source
    assert "估值折价反映资产质量担忧、息差收窄压力" in source