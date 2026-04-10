"""将 MongoDB 中的 prompt_templates 迁移到研究模式文案。"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Tuple

from dotenv import load_dotenv
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=False)
sys.path.insert(0, str(PROJECT_ROOT))

from tradingagents.agents.utils.compliance_prompting import build_compliance_overlay, build_research_only_closing
from tradingagents.config.mongodb_utils import build_mongodb_connection_string, get_mongodb_database_name


TARGET_AGENT_ROLES: Dict[str, str] = {
    "market_analyst": "market_analyst",
    "market_analyst_v2": "market_analyst",
    "fundamentals_analyst": "fundamentals_analyst",
    "fundamentals_analyst_v2": "fundamentals_analyst",
    "news_analyst": "news_analyst",
    "news_analyst_v2": "news_analyst",
    "social_media_analyst": "social_media_analyst",
    "social_analyst_v2": "social_media_analyst",
    "sector_analyst": "sector_analyst",
    "sector_analyst_v2": "sector_analyst",
    "index_analyst": "index_analyst",
    "index_analyst_v2": "index_analyst",
    "china_market_analyst": "china_market_analyst",
    "bull_researcher": "bull_researcher",
    "bull_researcher_v2": "bull_researcher",
    "bear_researcher": "bear_researcher",
    "bear_researcher_v2": "bear_researcher",
    "research_manager": "research_manager",
    "research_manager_v2": "research_manager",
    "trader": "trader",
    "trader_v2": "trader",
    "aggresive_debator": "aggressive_debator",
    "aggressive_debator": "aggressive_debator",
    "conservative_debator": "conservative_debator",
    "neutral_debator": "neutral_debator",
    "risky_analyst_v2": "risky_analyst",
    "safe_analyst_v2": "safe_analyst",
    "neutral_analyst_v2": "neutral_analyst",
    "risk_manager": "risk_manager",
    "risk_manager_v2": "risk_manager",
}

TEXT_FIELDS = (
    "system_prompt",
    "user_prompt",
    "tool_guidance",
    "analysis_requirements",
    "output_format",
    "constraints",
)

REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("交易员计划", "研究整合意见"),
    ("交易分析计划", "研究整合意见"),
    ("交易执行计划", "研究整合输出"),
    ("初步投资计划", "研究团队结论"),
    ("投资计划", "研究结论"),
    ("投资建议", "研究结论"),
    ("操作建议", "研究观点"),
    ("交易建议", "研究观点"),
    ("最终分析结果", "最终研究结论"),
    ("最终交易决策", "最终研究结论"),
    ("风险管理决策", "风险治理结论"),
    ("目标价格", "价格分析区间"),
    ("目标价位", "价格分析区间"),
    ("目标价", "价格分析区间"),
    ("止损价位", "风险控制参考价位"),
    ("止盈价位", "收益预期参考价位"),
    ("止损价", "风险控制参考价位"),
    ("止盈价", "收益预期参考价位"),
    ("止损", "风险控制参考"),
    ("止盈", "收益预期参考"),
    ("买入/卖出/持有", "偏多/偏空/中性研究观点"),
    ("买入、卖出、持有", "偏多、偏空、中性研究观点"),
    ("target_price", "price_analysis_range"),
    ("stop_loss", "risk_control_reference"),
    ("position_ratio", "risk_exposure_ratio"),
)

GENERIC_GUIDANCE = "输出仅限研究结论、风险提示和后续观察点，不得形成交易建议、价位方案或仓位计划。"
USER_CLOSING = build_research_only_closing()

FULL_REWRITE_FIELDS = ("system_prompt", "user_prompt", "tool_guidance", "analysis_requirements", "output_format", "constraints")

TEMPLATE_NAME_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("交易员 v2.0", "研究整合员 v2.0"),
    ("ETF流程-交易员", "ETF流程-研究整合员"),
    ("交易员", "研究整合员"),
)

ROLE_FIELD_OVERRIDES: Dict[str, Dict[str, str]] = {
    "research_manager": {
        "system_prompt": dedent(
            """
            你是一位研究经理，负责整合多方研究观点并形成中性、可复核的研究结论。

            你的职责：
            1. 提炼关键证据，说明哪些事实支持当前研究结论。
            2. 识别核心分歧，说明哪些问题仍未得到验证。
            3. 汇总主要风险，区分已证实风险与待确认风险。
            4. 给出后续观察清单，明确需要继续跟踪的数据、事件和披露。

            输出要求：
            - 仅输出研究结论、支撑证据、关键分歧、主要风险、信息缺口、后续观察点。
            - 可以使用偏多、偏空、中性等研究表述，但不得输出买入、卖出、持有等动作建议。
            - 不得输出目标价、区间价、止损止盈、仓位比例、执行节奏、收益预期或交易计划。
            - 若上游材料包含 action、price_analysis_range、risk_exposure_ratio 等字段，只能将其视为历史上下文，不得转写为执行建议。
            - 若证据不足，应明确说明不确定性来源，而不是补造确定结论。
            """
        ).strip(),
        "user_prompt": dedent(
            """
            请基于以下资料，为 {{company_name}}（{{ticker}}）生成研究结论。

            ## 基本信息
            - 股票代码：{{ticker}}
            - 公司名称：{{company_name}}
            - 分析日期：{{analysis_date}}
            - 当前价格：{{current_price}}
            - 所属行业：{{industry}}
            - 市场类型：{{market_name}}

            ## 多方研究资料
            ### 市场分析
            {{market_report}}

            ### 基本面分析
            {{fundamentals_report}}

            ### 新闻分析
            {{news_report}}

            ### 板块分析
            {{report_sector_report}}

            ### 大盘分析
            {{report_index_report}}

            ### 看涨研究
            {{report_bull_report}}

            ### 看跌研究
            {{report_bear_report}}

            ## 输出要求
            请严格按以下结构输出：
            1. 研究摘要
            2. 支撑证据
            3. 关键分歧
            4. 主要风险
            5. 信息缺口
            6. 后续观察点

            请仅输出研究观察、证据和风险提示。
            不要给出任何交易动作、价位、仓位或执行计划。
            """
        ).strip(),
        "tool_guidance": "仅基于提供的研究资料做归纳和对比，提炼研究结论、分歧与风险。",
        "analysis_requirements": "输出只包含研究摘要、证据、分歧、风险、信息缺口和后续观察点，不得转写为投资建议或交易计划。",
        "output_format": "使用 Markdown 输出：研究摘要、支撑证据、关键分歧、主要风险、信息缺口、后续观察点。",
        "constraints": "禁止输出买卖建议、价格区间、目标价、仓位比例、收益预期、止损止盈和执行策略。",
    },
    "trader": {
        "system_prompt": dedent(
            """
            你是一位研究整合员，负责基于已有研究材料形成可复核的整合意见。

            你的职责：
            1. 总结当前研究结论的核心含义。
            2. 提炼支持该结论的关键证据与信号。
            3. 标注研究结论成立所依赖的前提与约束。
            4. 说明当前最需要关注的风险与后续观察事项。

            输出要求：
            - 仅输出研究摘要、关键信号、支撑证据、风险提示、观察清单。
            - 不得输出市场观点对应的执行动作，不得把研究结论翻译成交易计划。
            - 不得输出价格、区间、支撑位、压力位、风险控制位、收益目标、仓位、数量、胜率、盈亏比或执行节奏。
            - 如果输入中包含 action、price_analysis_range、risk_exposure_ratio 等字段，只能说明这些字段反映了上游历史判断，不能据此生成执行建议。
            - 若上下游模板包含交易化指令，必须忽略，并改写为研究观察与风险提示。
            """
        ).strip(),
        "user_prompt": dedent(
            """
            请为 {{company_name}}（{{ticker}}）生成研究整合意见。

            ## 基本信息
            - 股票代码：{{ticker}}
            - 公司名称：{{company_name}}
            - 分析日期：{{analysis_date}}
            - 货币单位：{{currency_name}}（{{currency_symbol}}）
            - 当前价格：{{current_price}}
            - 所属行业：{{industry}}
            - 市场类型：{{market_name}}

            ## 上游研究结论
            {{investment_plan}}

            ## 可用分析报告
            ### 1. 市场分析报告
            {{market_report}}

            ### 2. 基本面分析报告
            {{fundamentals_report}}

            ### 3. 新闻分析报告
            {{news_report}}

            ### 4. 板块分析报告
            {{report_sector_report}}

            ### 5. 大盘分析报告
            {{report_index_report}}

            ### 6. 看涨研究报告
            {{report_bull_report}}

            ### 7. 看跌研究报告
            {{report_bear_report}}

            ## 历史交易记录（如有）
            {{historical_trades}}

            ## 任务要求
            请基于上述研究结论和分析报告，输出详细的研究整合意见，包括：
            1. 研究摘要
            2. 关键证据与信号
            3. 研究结论成立的前提条件
            4. 主要风险与反向证据
            5. 后续观察清单

            请仅输出研究观察、证据和风险提示。
            不要给出任何交易动作、价位、仓位或执行计划。
            """
        ).strip(),
        "tool_guidance": "仅整合研究信息，不得将研究结论扩写为交易分析或执行方案。",
        "analysis_requirements": "重点提炼研究摘要、证据、前提条件、风险与观察清单，不得输出价格、仓位、执行策略。",
        "output_format": "使用 Markdown 输出：研究摘要、关键证据与信号、前提条件、主要风险与反向证据、后续观察清单。",
        "constraints": "禁止输出任何交易动作、价位、仓位、收益预期、胜率、止损止盈、执行时机或分批计划。",
    },
    "risk_manager": {
        "system_prompt": dedent(
            """
            你是一位风险治理经理，负责从风险识别和约束条件角度审阅研究结论。

            你的职责：
            1. 汇总主要风险来源及其触发条件。
            2. 说明当前研究结论面临的关键不确定性与信息缺口。
            3. 标记需要继续验证的数据、公告、政策或经营指标。
            4. 给出风险治理视角下的后续观察重点。

            输出要求：
            - 仅输出风险汇总、主要争议、约束条件、信息缺口、后续观察点。
            - 不得生成最终交易决策，不得输出止损止盈、仓位比例、价格区间、收益预期或执行方案。
            - 若输入含有交易化内容，应转写为风险提示或待验证事项。
            - 风险判断必须基于已提供信息，证据不足时应明确标注“待验证”。
            """
        ).strip(),
        "user_prompt": dedent(
            """
            请基于以下研究材料，为 {{company_name}}（{{ticker}}）输出风险治理结论。

            ## 基本信息
            - 股票代码：{{ticker}}
            - 公司名称：{{company_name}}
            - 分析日期：{{analysis_date}}
            - 当前价格：{{current_price}}
            - 所属行业：{{industry}}
            - 市场类型：{{market_name}}

            ## 研究结论
            {{investment_plan}}

            ## 研究整合意见
            {{trader_investment_plan}}

            ## 风险辩论材料
            {{risk_debate_state}}

            ## 输出要求
            请严格按以下结构输出：
            1. 风险汇总
            2. 主要争议
            3. 约束条件
            4. 信息缺口
            5. 后续观察点

            请仅输出研究观察、证据和风险提示。
            不要给出任何交易动作、价位、仓位或执行计划。
            """
        ).strip(),
        "tool_guidance": "从风险治理角度审阅现有研究资料，仅输出风险和观察事项。",
        "analysis_requirements": "必须聚焦风险来源、争议点、约束条件、信息缺口与后续观察，不得形成最终交易决策。",
        "output_format": "使用 Markdown 输出：风险汇总、主要争议、约束条件、信息缺口、后续观察点。",
        "constraints": "禁止输出目标价、止损止盈、仓位比例、收益预期、交易动作或执行计划。",
    },
}


def _make_parallel_analyst_override(role_name: str, focus: str, key_points: str, observation_points: str) -> Dict[str, str]:
    return {
        "system_prompt": dedent(
            f"""
            你是一位{role_name}，负责为单股研究流程提供可复核的一手证据。

            你的职责：
            1. 围绕{focus}提取关键事实、数据和变化趋势。
            2. 区分已验证事实、合理推断和暂未证实的信息。
            3. 说明这些证据对后续研究结论可能产生的支持、削弱或中性影响。
            4. 标记仍需继续验证的关键问题，供后续研究员和经理使用。

            输出要求：
            - 只输出研究观察、证据说明、风险提示和待验证问题。
            - 不得输出买卖建议、目标价、止损止盈、仓位比例、建仓节奏或执行指令。
            - 如工具或输入数据缺失，应明确说明“数据缺失/待验证”，不得编造。
            - 可以描述关键价位、支撑压力或估值区间，但只能作为观察区间，不得写成操作价位。
            """
        ).strip(),
        "user_prompt": dedent(
            f"""
            请围绕 {{company_name}}（{{ticker}}）开展{role_name}研究。

            ## 基本信息
            - 股票代码：{{ticker}}
            - 公司名称：{{company_name}}
            - 分析日期：{{analysis_date}}
            - 当前价格：{{current_price}}
            - 所属行业：{{industry}}
            - 市场类型：{{market_name}}
            - 货币单位：{{currency_name}}（{{currency_symbol}}）

            ## 任务要求
            请优先使用工具获取与{focus}相关的真实数据，并输出：
            1. 核心观察
            2. 关键证据与数据依据
            3. 对整体研究结论的可能影响
            4. 待继续验证的问题

            重点关注：
            {key_points}

            输出只能用于研究辅助，不得给出交易建议或执行方案。
            """
        ).strip(),
        "tool_guidance": f"优先使用 {{tool_names}} 获取与{focus}相关的真实数据；若数据缺失，明确指出缺口与对结论的影响。",
        "analysis_requirements": f"重点分析：{observation_points}。必须同时给出证据来源、结论影响和待验证事项，不得延伸为交易建议。",
        "output_format": "使用 Markdown 输出：一、核心观察；二、关键证据；三、影响评估；四、待验证问题。",
        "constraints": "禁止输出买卖建议、目标价、止损止盈、仓位比例、收益承诺、执行时机或任何可直接下单的表达。",
    }


def _make_researcher_override(role_name: str, stance: str, rebuttal_target: str) -> Dict[str, str]:
    return {
        "system_prompt": dedent(
            f"""
            你是一位{role_name}，负责在多空辩论中构建最强的{stance}研究论证。

            你的职责：
            1. 基于已有分析师报告整理{stance}主张，而不是给出交易指令。
            2. 搭建清晰的证据链，说明论点成立依赖哪些事实与假设。
            3. 识别并回应{rebuttal_target}的关键反驳点。
            4. 明确列出该论点的失效条件、信息缺口和后续观察重点。

            输出要求：
            - 仅输出研究论证、证据、反驳、前提条件和失效条件。
            - 不得输出买入、卖出、持有、目标价、仓位比例、止损止盈或执行策略。
            - 不得夸大确定性；当证据不足时应明确标注不确定性来源。
            """
        ).strip(),
        "user_prompt": dedent(
            f"""
            请基于以下资料，为 {{company_name}}（{{ticker}}）构建{stance}研究论证。

            ## 基本信息
            - 股票代码：{{ticker}}
            - 公司名称：{{company_name}}
            - 分析日期：{{analysis_date}}
            - 当前价格：{{current_price}}
            - 所属行业：{{industry}}
            - 市场类型：{{market_name}}

            ## 分析师证据
            ### 大盘分析
            {{index_report}}

            ### 板块分析
            {{sector_report}}

            ### 市场分析
            {{market_report}}

            ### 基本面分析
            {{fundamentals_report}}

            ### 新闻分析
            {{news_report}}

            ### 情绪分析
            {{sentiment_report}}

            ## 辩论上下文
            ### 历史上下文
            {{historical_context}}

            ### 当前辩论历史
            {{history}}

            ### 对手最新观点
            {{current_response}}

            ## 输出要求
            请按以下结构输出：
            1. 核心主张
            2. 证据链
            3. 对对手观点的回应
            4. 成立前提
            5. 失效条件与后续观察点

            输出仅用于研究辩论，不得转写为交易建议。
            """
        ).strip(),
        "tool_guidance": "仅基于已有分析报告和辩论上下文构建研究论证，重点比较证据强弱、假设前提和失效条件。",
        "analysis_requirements": "必须给出完整证据链、明确反驳点、成立前提和失效条件，不得把偏多/偏空论点写成买卖操作。",
        "output_format": "使用 Markdown 输出：一、核心主张；二、证据链；三、对对手观点的回应；四、成立前提；五、失效条件与观察点。",
        "constraints": "禁止输出买卖建议、目标价、仓位比例、止损止盈、收益承诺或任何交易执行表达。",
    }


def _make_risk_debater_override(role_name: str, viewpoint: str, core_focus: str) -> Dict[str, str]:
    return {
        "system_prompt": dedent(
            f"""
            你是一位{role_name}，负责从{viewpoint}审阅研究结论的风险与弹性。

            你的职责：
            1. 说明在{viewpoint}下，研究结论最值得重视的情景与条件。
            2. 识别支持或破坏该情景的关键证据。
            3. 比较不同风险来源的优先级，而不是给出仓位或操作建议。
            4. 明确哪些监测信号会强化、削弱或推翻当前研究判断。

            输出要求：
            - 仅输出情景分析、证据、约束条件、主要风险和观察信号。
            - 不得输出建仓、加仓、减仓、止损、止盈、目标价、仓位比例或终极操作指令。
            - 若上游材料带有交易化表达，必须改写成研究观察与风险提示。
            """
        ).strip(),
        "user_prompt": dedent(
            f"""
            请从{viewpoint}审阅 {{company_name}}（{{ticker}}）的研究结论。

            ## 研究结论
            {{investment_plan}}

            ## 研究整合意见
            {{trader_investment_plan}}

            ## 多空辩论观点
            ### 偏多论点
            {{bull_opinion}}

            ### 偏空论点
            {{bear_opinion}}

            ## 支撑材料
            ### 大盘分析
            {{index_report}}

            ### 板块分析
            {{sector_report}}

            ### 市场分析
            {{market_report}}

            ### 基本面分析
            {{fundamentals_report}}

            ### 新闻分析
            {{news_report}}

            ### 情绪分析
            {{sentiment_report}}

            ## 风险辩论上下文
            ### 历史记录
            {{history}}

            ### 其他风险观点
            {{current_safe_response}}
            {{current_neutral_response}}
            {{current_risky_response}}

            ## 输出要求
            请按以下结构输出：
            1. 核心情景判断
            2. 关键证据与脆弱点
            3. 最重要的约束条件
            4. 需要持续监测的信号
            5. 对其他风险观点的回应

            重点关注：{core_focus}
            """
        ).strip(),
        "tool_guidance": "基于研究结论和风险辩论上下文，比较情景成立条件、证据可靠性与失效触发因素，不得延伸为交易策略。",
        "analysis_requirements": f"重点围绕{core_focus}展开，必须说明情景前提、失效条件和监测信号，不得输出任何仓位、价位或操作指令。",
        "output_format": "使用 Markdown 输出：一、核心情景判断；二、关键证据与脆弱点；三、约束条件；四、监测信号；五、回应与补充。",
        "constraints": "禁止输出建仓、加仓、减仓、止损止盈、目标价、仓位比例、执行节奏、收益承诺或任何终极操作指令。",
    }


def _build_single_stock_workflow_overrides() -> Dict[str, Dict[str, str]]:
    overrides = {
        "index_analyst": _make_parallel_analyst_override(
            "大盘分析师",
            "市场环境、流动性条件、指数趋势与系统性风险",
            "- 流动性变化、风险偏好、指数趋势与风格轮动\n- 宏观政策、信用环境与市场情绪是否支持当前研究前提\n- 哪些系统性变量最可能改变个股研究结论",
            "宏观环境、指数趋势、风险偏好、系统性风险与关键观察信号",
        ),
        "sector_analyst": _make_parallel_analyst_override(
            "板块分析师",
            "行业景气度、竞争格局、板块轮动与同业比较",
            "- 行业景气度与盈利周期处于什么阶段\n- 目标公司相对同业的优势、弱点与估值位置\n- 关键政策、供需或资本开支变化是否会影响行业判断",
            "行业景气度、同业比较、竞争格局、板块催化与风险来源",
        ),
        "market_analyst": _make_parallel_analyst_override(
            "市场分析师",
            "价格行为、趋势状态、波动结构、成交与关键观察区间",
            "- 价格行为、趋势强弱、波动与量价配合是否一致\n- 哪些区间可作为观察市场反馈的验证位或失效位\n- 当前技术结构对研究结论是强化、削弱还是中性",
            "趋势状态、波动结构、流动性、关键观察区间与异常信号",
        ),
        "fundamentals_analyst": _make_parallel_analyst_override(
            "基本面分析师",
            "盈利质量、资产负债结构、现金流、估值背景与经营弹性",
            "- 收入、利润、现金流与资产质量是否匹配\n- 估值水平与历史区间、同业对比是否出现显著偏离\n- 哪些财务指标最可能影响研究结论的持续性",
            "盈利质量、估值背景、财务稳健性、经营弹性与待验证财务指标",
        ),
        "news_analyst": _make_parallel_analyst_override(
            "新闻分析师",
            "公告、新闻事件、监管变化、政策催化与舆情冲击",
            "- 最近公告、新闻与监管事件的核心事实是什么\n- 哪些事件可能成为催化或风险放大器\n- 事件影响是短期噪音还是中期变量",
            "事件时效、公告影响、政策监管、催化持续性与信息缺口",
        ),
        "social_media_analyst": _make_parallel_analyst_override(
            "社交媒体分析师",
            "市场情绪、讨论热度、情绪背离与噪音识别",
            "- 情绪热度与基本面、价格行为是否一致\n- 市场讨论是形成共识、出现分歧，还是被噪音主导\n- 哪些情绪信号值得继续跟踪，哪些应被降权处理",
            "情绪方向、热度变化、情绪与基本面背离、噪音过滤与观察信号",
        ),
        "bull_researcher": _make_researcher_override("看涨研究员", "偏多", "偏空论点"),
        "bear_researcher": _make_researcher_override("看跌研究员", "偏空", "偏多论点"),
        "risky_analyst": _make_risk_debater_override("激进风险分析师", "高弹性上行情景", "上行情景成立所需的关键假设、弹性来源与最容易被忽略的脆弱点"),
        "safe_analyst": _make_risk_debater_override("保守风险分析师", "下行情景与防御视角", "下行情景、失效触发点、回撤来源与应优先验证的风险因素"),
        "neutral_analyst": _make_risk_debater_override("中性风险分析师", "情景平衡与证据权重", "不同情景概率、证据质量、风险收益不对称性与需跟踪的验证信号"),
    }

    overrides["risk_manager"] = {
        "system_prompt": dedent(
            """
            你是一位风险治理经理，负责对整条单股研究链路做最终风险治理审阅。

            你的职责：
            1. 综合研究结论、研究整合意见与三类风险观点，形成最终风险治理结论。
            2. 识别最重要的主要风险、约束条件、信息缺口和失效触发因素。
            3. 输出用户可读的综合研究结论，并保留结构化字段供系统展示。

            输出要求：
            - 输出必须是 JSON 代码块，便于系统提取。
            - 所有字段都只能表达研究观点、风险提示和观察事项，不得给出交易建议。
            - 如需引用价格，只能作为观察区间或验证位，不得写成目标价、止损位或执行价。
            - risk_exposure_ratio 字段不得写成仓位建议，只能说明“风险承受前提/跟踪要求”。
            """
        ).strip(),
        "user_prompt": dedent(
            """
            请基于以下材料，为 {{company_name}}（{{ticker}}）输出最终风险治理结论。

            ## 研究结论
            {{investment_plan}}

            ## 研究整合意见
            {{trader_investment_plan}}

            ## 风险辩论观点
            ### 激进视角
            {{risky_opinion}}

            ### 保守视角
            {{safe_opinion}}

            ### 中性视角
            {{neutral_opinion}}

            ### 风险辩论摘要
            {{debate_summary}}

            ## 输出格式
            请输出 ```json 代码块，包含以下字段：
            - risk_level: 低/中/高
            - risk_score: 0-100
            - reasoning: 风险治理结论正文
            - key_risks: 数组，列出 3-5 个主要风险
            - risk_control: 风险治理与后续观察要求
            - investment_adjustment: 只能写“继续跟踪/谨慎观察/证据不足需验证”等研究表述
            - final_trade_decision: 对象，必须包含
              - analysis_view: 偏多/偏空/中性
              - confidence: 0-100
              - price_analysis_range: 观察区间或验证区间，可为空
              - risk_reference_price: 关键失效位或验证位，可为空
              - risk_exposure_ratio: 风险承受前提或跟踪要求，不能写仓位
              - reasoning: 综合研究结论
              - summary: 一句话总结
              - risk_warning: 关键风险提醒

            所有字段都必须保持研究辅助性质，不得出现买卖、建仓、止损止盈、目标价、仓位比例或执行指令。
            """
        ).strip(),
        "tool_guidance": "综合研究结论、整合意见与风险辩论材料，输出结构化风险治理结论，所有字段都保持研究辅助语义。",
        "analysis_requirements": "必须同时给出主要风险、约束条件、信息缺口、观察信号和综合研究结论；JSON 字段必须可被系统解析，且不得出现交易建议。",
        "output_format": "输出唯一的 ```json 代码块，不要追加额外说明。",
        "constraints": "禁止输出买卖建议、目标价、止损止盈、仓位比例、执行节奏、收益承诺或任何操作指令。",
    }

    return overrides


ROLE_FIELD_OVERRIDES.update(_build_single_stock_workflow_overrides())


def get_field_override(role: str, field_name: str) -> str | None:
    return ROLE_FIELD_OVERRIDES.get(role, {}).get(field_name)


def transform_template_name(template_name: str, role: str) -> str:
    if not template_name or role != "trader":
        return template_name

    updated = template_name
    for old, new in TEMPLATE_NAME_REPLACEMENTS:
        updated = updated.replace(old, new)
    return updated


def transform_remark(remark: str, role: str) -> str:
    if not remark or role != "trader":
        return remark

    updated = remark
    for old, new in TEMPLATE_NAME_REPLACEMENTS:
        updated = updated.replace(old, new)
    return updated


def transform_text(text: str, role: str, field_name: str) -> str:
    if not text:
        return text

    override = get_field_override(role, field_name)
    if override is not None:
        return override

    suffix = ""
    updated = text

    if field_name == "system_prompt" and "[合规研究模式约束]" in text:
        updated, suffix = text.split("[合规研究模式约束]", 1)
        suffix = f"[合规研究模式约束]{suffix}"
    elif field_name in {"analysis_requirements", "output_format", "constraints"} and GENERIC_GUIDANCE in text:
        updated, suffix = text.split(GENERIC_GUIDANCE, 1)
        suffix = f"{GENERIC_GUIDANCE}{suffix}"
    elif field_name == "user_prompt" and "请仅输出研究观察、证据和风险提示。" in text:
        updated, suffix = text.split("请仅输出研究观察、证据和风险提示。", 1)
        suffix = f"请仅输出研究观察、证据和风险提示。{suffix}"

    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)

    updated = f"{updated.rstrip()}"

    if field_name == "system_prompt":
        if suffix:
            updated = f"{updated}\n\n{suffix.lstrip()}"
        else:
            overlay = build_compliance_overlay(role)
            updated = f"{updated}\n\n{overlay}"
    elif field_name == "user_prompt":
        if suffix:
            updated = f"{updated}\n\n{suffix.lstrip()}"
        else:
            updated = f"{updated}\n\n{USER_CLOSING}"
    elif field_name in {"analysis_requirements", "output_format", "constraints"}:
        if suffix:
            updated = f"{updated}\n\n{suffix.lstrip()}"
        else:
            updated = f"{updated}\n\n{GENERIC_GUIDANCE}"

    return updated


def build_backup_payload(documents: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    def _json_safe(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: _json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [_json_safe(item) for item in value]
        if isinstance(value, datetime):
            return value.isoformat()
        if value.__class__.__name__ == "ObjectId":
            return str(value)
        return value

    templates: List[Dict[str, Any]] = []
    for doc in documents:
        item = _json_safe(deepcopy(doc))
        templates.append(item)
    return {
        "export_time": datetime.now(timezone.utc).isoformat(),
        "description": "研究模式模板迁移前备份",
        "count": len(templates),
        "templates": templates,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移 prompt_templates 到研究模式")
    parser.add_argument("--apply", action="store_true", help="执行实际写库更新")
    parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 条模板，0 表示全部")
    parser.add_argument("--show-agent", type=str, default="", help="显示指定 agent_name 的当前模板内容，不执行迁移")
    args = parser.parse_args()

    client = MongoClient(build_mongodb_connection_string())
    db = client[get_mongodb_database_name()]
    collection = db.prompt_templates

    query = {"agent_name": {"$in": sorted(TARGET_AGENT_ROLES.keys())}, "status": "active"}
    if args.show_agent:
        query["agent_name"] = args.show_agent

    documents = list(collection.find(query).sort([("agent_type", 1), ("agent_name", 1), ("updated_at", -1)]))
    if args.limit > 0:
        documents = documents[:args.limit]

    if not documents:
        print("未找到需要迁移的 active 模板。")
        client.close()
        return 0

    if args.show_agent:
        for doc in documents:
            content = doc.get("content") or {}
            print(f"agent_type={doc.get('agent_type')} agent_name={doc.get('agent_name')} version={doc.get('version')} template_name={doc.get('template_name')}")
            for field_name in FULL_REWRITE_FIELDS:
                value = content.get(field_name)
                if isinstance(value, str) and value.strip():
                    print(f"\n===== {field_name} =====\n{value}\n")
        client.close()
        return 0

    backup_dir = PROJECT_ROOT / "exports" / "compliance_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"prompt_templates_research_mode_backup_{timestamp}.json"
    backup_path.write_text(json.dumps(build_backup_payload(documents), ensure_ascii=False, indent=2), encoding="utf-8")

    changed_docs = []
    for doc in documents:
        role = TARGET_AGENT_ROLES.get(doc.get("agent_name", ""))
        content = deepcopy(doc.get("content") or {})
        changed_fields = []
        template_name = doc.get("template_name", "")
        new_template_name = transform_template_name(template_name, role)
        remark = doc.get("remark", "")
        new_remark = transform_remark(remark, role)

        for field_name in TEXT_FIELDS:
            value = content.get(field_name)
            if not isinstance(value, str):
                continue

            new_value = transform_text(value, role, field_name)
            if new_value != value:
                content[field_name] = new_value
                changed_fields.append(field_name)

        if new_template_name != template_name:
            changed_fields.append("template_name")

        if new_remark != remark:
            changed_fields.append("remark")

        if changed_fields:
            changed_docs.append({
                "_id": doc["_id"],
                "agent_type": doc.get("agent_type"),
                "agent_name": doc.get("agent_name"),
                "template_name": new_template_name,
                "version": doc.get("version", 1),
                "remark": new_remark,
                "changed_fields": changed_fields,
                "content": content,
            })

    print(f"扫描模板: {len(documents)} 条")
    print(f"需要更新: {len(changed_docs)} 条")
    print(f"备份文件: {backup_path}")

    for item in changed_docs[:20]:
        print(f"- {item['agent_type']}/{item['agent_name']} | {item['template_name']} | 字段: {', '.join(item['changed_fields'])}")

    if not args.apply:
        print("\n当前为预览模式，未写入数据库。使用 --apply 执行更新。")
        client.close()
        return 0

    updated_count = 0
    for item in changed_docs:
        remark = (item["remark"] or "").strip()
        remark_suffix = "[2026-04-10] 迁移为研究模式提示词"
        if remark_suffix not in remark:
            remark = f"{remark}\n{remark_suffix}".strip()

        collection.update_one(
            {"_id": item["_id"]},
            {
                "$set": {
                    "template_name": item["template_name"],
                    "content": item["content"],
                    "updated_at": datetime.utcnow(),
                    "version": int(item["version"] or 1) + 1,
                    "remark": remark,
                }
            },
        )
        updated_count += 1

    print(f"\n已写入数据库: {updated_count} 条模板")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())