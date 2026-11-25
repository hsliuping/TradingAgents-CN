from core.agents.analyst import AnalystAgent
from core.agents.base import GENERIC_REPORT_FALLBACK
"""
市场分析师Agent v2.0

基于AnalystAgent基类实现的市场分析师
使用配置驱动的方式，支持动态工具绑定
"""

import logging
import re
from typing import Any, Dict, Optional

from langchain_core.messages import SystemMessage, HumanMessage
from ..analyst import AnalystAgent
from ..config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from ..registry import register_agent

logger = logging.getLogger(__name__)

_MARKET_REPORT_SANITIZE_RULES = [
    (r"价格区间", "波动范围"),
    (r"支撑位", "支撑关系"),
    (r"阻力位", "压力关系"),
    (r"关键价位", "关键价格关系"),
    (r"风险控制位", "风险观察位置"),
    (r"价格分析区间", "历史波动区间"),
    (r"尚未站上\s*(MA\d+)", r"仍低于\1"),
    (r"尚未突破\s*(MA\d+)", r"仍低于\1"),
    (r"重新站上\s*(MA\d+)", r"回到\1上方"),
    (r"站上\s*(MA\d+)", r"高于\1"),
    (r"尚未站稳于\s*(MA\d+)(?:之上|上方)?", r"仍低于\1"),
    (r"未能有效站稳于其上方", "与该均线的关系仍待改善"),
    (r"未能有效站稳于\s*(MA\d+)(?:之上|上方)?", r"与\1的关系仍待改善"),
    (r"站稳\s*(MA\d+)", r"高于\1"),
    (r"站稳于\s*(MA\d+)(?:之上|上方)?", r"高于\1"),
    (r"站稳信号", "关系改善信号"),
    (r"能否实现有效站稳", "短期均线关系是否改善"),
    (r"尚未形成有效突破(?:信号|支撑)", "上破依据仍不足"),
    (r"未形成有效突破信号", "上破依据仍不足"),
    (r"未形成有效突破支撑", "上破依据仍不足"),
    (r"未形成有效突破", "上破依据仍不足"),
    (r"有效突破", "明确上破"),
    (r"强势突破", "明显上破"),
    (r"对关键短期均线的突破", "对关键短期均线关系的改善"),
    (r"对短期均线上方的确认", "与短期均线关系改善的确认"),
    (r"上行突破动力", "进一步走强依据"),
    (r"未突破布林带上轨", "仍低于布林带上轨"),
    (r"突破布林带上轨", "高于布林带上轨"),
    (r"持续运行于", "位于"),
    (r"柱状图是否(?:出现)?持续放大或收缩", "动能一致性是否增强或减弱"),
    (r"柱状图是否(?:出现)?持续放大", "动能一致性是否增强"),
    (r"MACD柱状图若继续持续放大", "MACD动能若进一步增强"),
    (r"持续放大", "进一步增强"),
    (r"持续收缩", "进一步减弱"),
    (r"未能维持站稳", "关系仍待改善"),
    (r"上行空间受限", "短期弹性受限"),
    (r"上行空间支撑", "偏积极支撑"),
    (r"上行支撑力", "偏积极支撑"),
    (r"上行空间", "进一步抬升弹性"),
    (r"较前期有所收窄，表明短期波动趋于收敛", "显示短期波动集中在当前区间内"),
    (r"向上排列趋势", "偏强排列"),
    (r"未形成明确上升趋势", "后续是否形成明确上行方向仍待验证"),
    (r"增强了市场信心", "为研究判断提供了一定技术支撑"),
]

# 尝试导入工具函数
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None

# 不再需要直接导入 get_agent_prompt，使用基类的 _get_prompt_from_template 方法


@register_agent
class MarketAnalystV2(AnalystAgent):
    """
    市场分析师 v2.0

    功能：
    - 分析股票的价格走势
    - 分析技术指标
    - 分析成交量
    - 生成市场分析报告

    工作流程：
    1. 调用工具获取价格数据、技术指标、成交量数据
    2. 使用LLM分析数据
    3. 生成市场分析报告

    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent_with_dynamic_tools

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent_with_dynamic_tools("market_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="market_analyst_v2",
        name="市场分析师 v2.0",
        description="分析股票的价格走势、技术指标和成交量，生成市场分析报告",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=[
            "get_stock_market_data_unified"
        ],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="market_report", type="string", description="市场分析报告"),
        ],
        requires_tools=True,
        output_field="market_report",
        report_label="【市场分析 v2】",
        workflow_stage="analyst",
    )

    # 分析师类型
    analyst_type = "market"

    # 输出字段名
    output_field = "market_report"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        覆盖执行逻辑以支持模板调试与提示词覆盖
        """
        try:
            ticker, analysis_date = self._extract_common_params(state)

            market_type = state.get("market_type", "A股")
            context = state.get("context")
            overrides = state.get("prompt_overrides") or {}
            system_override = overrides.get("system")
            user_override = overrides.get("user")
            analysis_override = overrides.get("analysis")

            if not ticker:
                raise ValueError("Missing required parameters: ticker")

            system_prompt = system_override
            if not system_prompt:
                # 🔑 从 state 中提取必要的变量（系统变量应该在工作流创建时已经准备好）
                template_variables = {}
                
                # 基础变量
                if "ticker" in state:
                    template_variables["ticker"] = state["ticker"]
                else:
                    template_variables["ticker"] = ticker
                
                # 日期相关
                if "analysis_date" in state or "trade_date" in state:
                    analysis_date = state.get("analysis_date") or state.get("trade_date")
                    if analysis_date:
                        if isinstance(analysis_date, str) and len(analysis_date) > 10:
                            analysis_date = analysis_date.split()[0]
                        template_variables["current_date"] = analysis_date
                        template_variables["analysis_date"] = analysis_date
                else:
                    current_date = state.get("current_date", analysis_date)
                    template_variables["current_date"] = current_date
                    template_variables["analysis_date"] = analysis_date
                    template_variables["start_date"] = state.get("start_date", current_date)
                
                # 公司信息（从 state 中获取，工作流引擎应该已经准备好）
                template_variables["company_name"] = state.get("company_name", "")
                template_variables["market_name"] = state.get("market_name", market_type)
                template_variables["currency_name"] = state.get("currency_name", "人民币")
                template_variables["currency_symbol"] = state.get("currency_symbol", "¥")
                template_variables["tool_names"] = ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
                
                system_prompt = self._get_prompt_from_template(
                    agent_type="analysts_v2",
                    agent_name="market_analyst_v2",
                    variables=template_variables,  # 传递必要的变量
                    state=state,  # 🔑 传递 state，基类会自动提取系统变量
                    context=context,
                    fallback_prompt=None,
                    prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
                )

            if not system_prompt:
                # 🔑 传递 state 给 _build_system_prompt，以便从 state 中提取变量完善模板
                system_prompt = self._build_system_prompt(market_type, context=context, state=state)

            user_prompt = user_override
            if not user_prompt:
                user_prompt = self._build_user_prompt(ticker, analysis_date, state)

            analysis_prompt = analysis_override or self._build_analysis_prompt(ticker)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            logger.info(f"系统提示词: {system_prompt}")
            logger.info(f"用户提示词: {user_prompt}")            

            if self._llm:
                if self._langchain_tools:
                    report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                else:
                    response = self._invoke_llm_with_trace(messages)
                    report = response.content if hasattr(response, 'content') else str(response)
            else:
                raise ValueError("LLM not initialized")

            report = self._sanitize_report(report)

            result = {self.output_field: report}
            # 🆕 附带工具调用摘要
            tool_summary = self._format_tool_call_summary()
            if tool_summary:
                result["tool_call_summaries"] = {self.analyst_type: tool_summary}
            return result

        except Exception as e:
            logger.error(f"[{self.agent_id}] 执行失败: {e}", exc_info=True)
            return {self.output_field: GENERIC_REPORT_FALLBACK}

    def _build_system_prompt(self, market_type: str = None, context=None, state: Dict[str, Any] = None) -> str:
        """
        构建系统提示词（参考 fundamentals_analyst_v2 的实现）

        Args:
            market_type: 市场类型（A股/港股/美股）（保留以兼容基类）
            context: AgentContext 对象（用于调试模式）
            state: 工作流状态（用于提取模板变量）
            
        Returns:
            系统提示词
        """
        logger.info("🔍 [MarketAnalystV2] 开始构建系统提示词")
        
        if state is None:
            state = {}
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        # 注意：虽然系统提示词通常不需要变量，但某些模板可能需要 ticker、current_date 等
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        template_variables = {}
        
        # 如果 state 中有 ticker 和 analysis_date，提取它们（系统提示词模板可能需要）
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        if "company_name" in state:
            template_variables["company_name"] = state["company_name"]
        if "analysis_date" in state or "trade_date" in state:
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                # 确保日期格式正确
                if isinstance(analysis_date, str) and len(analysis_date) > 10:
                    analysis_date = analysis_date.split()[0]
                template_variables["current_date"] = analysis_date
                template_variables["analysis_date"] = analysis_date
        if state.get("market_name"):
            template_variables["market_name"] = state["market_name"]
        if state.get("currency_name"):
            template_variables["currency_name"] = state["currency_name"]
        if state.get("currency_symbol"):
            template_variables["currency_symbol"] = state["currency_symbol"]
        if self._langchain_tools:
            template_variables["tool_names"] = ", ".join([t.name for t in self._langchain_tools])
        
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="market_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=context or state.get("context"),  # 优先使用传入的 context，否则从 state 获取
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )

        if prompt:
            return prompt

        # 默认提示词
        return f"""你是一位专业的{market_type}市场分析师，擅长技术分析。

你的职责：
1. 分析股票的价格走势（涨跌幅、趋势方向）
2. 分析技术指标（MA、MACD、RSI、KDJ等）
3. 分析成交量（放量、缩量、量价关系）
4. 综合判断市场情绪和趋势

分析要求：
- 客观、专业、基于数据
- 指出关键的技术信号
- 给出明确的趋势判断
- 使用中文输出

输出格式：
请以结构化的方式输出分析报告，包括：
- 价格走势分析
- 技术指标分析
- 成交量分析
- 综合判断
"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 和 fundamentals_analyst_v2 的实现）

        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            state: 工作流状态（用于提取模板变量）

        Returns:
            用户提示词
        """
        logger.info("🔍 [MarketAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        market_name = "中国A股"
        company_name = str(
            state.get("company_name")
            or state.get("stock_name")
            or state.get("name")
            or ""
        )
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                market_name = market_info.get('market_name', "中国A股")
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
                market_company_name = str(market_info.get("company_name") or "").strip()
                lookup_company_name = ""
                if not market_company_name:
                    lookup_company_name = str(self._get_company_name(ticker, market_info) or "").strip()

                if market_company_name:
                    company_name = market_company_name
                elif lookup_company_name and (not company_name or company_name == ticker or company_name.isdigit()):
                    # company_name 为空、等于 ticker 代码或纯数字时，均应使用 DB 查到的真实名称
                    company_name = lookup_company_name
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")

        if not company_name:
            company_name = ticker
        if not market_name:
            market_name = "未知市场"
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": analysis_date,
            "current_date": analysis_date,
            "start_date": "",  # 可以计算1年前的日期
            "currency_name": currency_name,
            "currency_symbol": currency_symbol,
            "tool_names": ", ".join([t.name for t in self._langchain_tools]) if self._langchain_tools else ""
        }
        
        # 使用基类的通用方法获取用户提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        # 🔑 注意：工具返回的数据会通过 ToolMessage 传递，不需要在 user_prompt 中检查
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="market_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取市场分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认提示词（不再检查 tool_data，因为工具数据会通过 ToolMessage 传递）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        return f"""请分析 {company_name}（{ticker}）在 {analysis_date} 的市场表现：

股票代码：{ticker}
公司名称：{company_name}
分析日期：{analysis_date}
市场类型：{market_name}

请调用工具获取市场数据，然后生成详细的市场分析报告。"""

    def _build_analysis_prompt(self, ticker: str) -> str:
        """构建工具调用后的专业分析提示词。"""
        return f"""基于获取的数据，请生成 {ticker} 的专业市场结构研究报告，包括：

1. 股票基本信息
2. 技术指标分析
    - 移动平均线（MA）分析
    - MACD指标分析
    - RSI相对强弱指标
    - 布林带（BOLL）分析
3. 价格趋势分析
    - 短期趋势（5-10个交易日）
    - 中期趋势（20-60个交易日）
    - 成交量分析
4. 综合评估
5. 对整体研究结论的影响
6. 后续观察点

如果工具返回的实际数据日期不同于分析日期，必须在正文中明确写出实际数据日期。
股票基本信息中的实际数据日期只能引用工具明确返回的“实际数据日期”或“最新有效日线日期”；如果分析日期是今天但工具显示最新有效日线仍为更早日期，禁止把分析日期直接写成实际数据日期。
如果某项价格、指标或成交字段缺失，请直接写“工具结果未提供”或“该维度仍待验证”，不要自行补全。
如果短期与中期信号冲突，必须明确写出冲突点以及为什么不能下更强结论。
股票基本信息部分要写明公司名称、股票代码、所属市场、实际数据日期、当前价格、涨跌幅和成交量。
技术指标分析部分要尽量完整覆盖 MA、MACD、RSI、BOLL 中工具已返回的内容，不要只写笼统总结。
价格趋势分析部分要覆盖短期趋势、中期趋势和成交量分析，保留最近5日高低点、均价或价格重心变化等事实数据。
如果工具只提供当前值、最近5日统计或单次快照，不得写“持续放大”“继续扩大”“连续多个交易日”“始终运行于”“站稳”“有效突破”“跌破失守”等需要更长时序验证的措辞。
均线排列关系与均线斜率方向要分开表述；若没有更长历史序列，不要把“MA20 高于 MA60”直接写成“MA60 向上运行”或“中期趋势已扭转”。
若工具结果中已包含“均线方向结论（工具端确定性计算）”，必须直接引用该结论，不要自行二次计算MA斜率或拐头。
若工具结果中包含“MACHINE_READABLE_MA_CONCLUSIONS”字段块，应优先按该字段块直接引用 MA5/MA10/MA20/MA60 的方向与拐头结论，不要自行从原始价格再推导。
若工具结果中包含“MACHINE_READABLE_MACD_CONCLUSIONS”字段块，应优先引用其中的 `macd.cross_signal`、`macd.dif_dea_relation`、`macd.hist_trend`，不要自行判断金叉/死叉。
凡是写到价格、均线或最近5日高低点的大小规律，必须先按工具给出的真实数值核对；后续文字必须与表格和数值一致。若无法确保完整排序正确，就只写逐项高于/低于关系，不要强行写链式排列。
不得写出与真实数值相反的比较式；例如 MA20 高于 MA60 时，不能写成“MA60 高于 MA20”。
只有工具明确提供价格与指标拐点对应关系或直接识别结果时，才可使用“背离”一词；否则改写为“信号分化”或“尚未形成一致验证”。
可以写最近5日历史高低点形成的历史波动区间，但不得写未来价格分析区间、关键触发区间或执行阈值。
如果工具只给出最近5日最高价、最低价、均价或当前价格与均线位置，只能写“最高价为”“触及”“位于”“高于/低于”“接近”等事实，不得改写成“短暂突破”“重新站稳”“持续运行于”等确认式措辞。
若工具未直接返回逐日穿越或阈值验证事实，不要写“曾一度突破MA5”“未能维持站稳”“有效站稳关键短期均线”等过程化表述；改写为当前价格与均线的相对关系及仍待验证事项。
只要描述价格与均线、布林带或历史区间的相对关系，优先使用“高于/低于”“位于”“接近”“处于区间中上部”“关系仍待改善”等表述，不要使用“站上”“站稳”“强势突破”“有效突破”“持续运行于”“持续放大”“上行空间”这类阈值或空间化措辞。
允许引用真实数值做事实说明，但不要把数值写成投资评级、目标价、价格分析区间、支撑阻力位、关键执行位、风险控制位或交易触发条件。
请使用研究口径解释趋势、结构、动能和量价关系，不要把“突破、跌破、站稳、失守、回踩确认、放量突破”写成执行方案。
`综合评估` 只归纳技术状态、主要强弱信号和冲突点，不要逐段重复前文指标解释；`对整体研究结论的影响` 只说明这些信号如何强化、削弱或中性影响整体研究，避免重复复述整套指标。
后续观察点不要写成“是否站稳于MA5之上”“是否持续运行于MA10与MA20之上”“若价格创新高则背离”等阈值句式；改写为关系是否改善、量价是否继续一致、指标同步性是否增强或减弱等可复核方向。
即便是否定句，也不要写“未形成有效突破”“未站稳于MA5之上”“MACD柱状图未持续放大”；改写为“上破证据仍不足”“价格与MA5关系仍待改善”“MACD当前为正值但延续性仍待验证”。
正文与后续观察点都不要写“尚未站稳于MA5之上”“未能有效站稳关键短期均线”“能否实现有效站稳”“柱状图是否出现持续放大”；改写为“价格低于MA5，短期均线关系仍待改善”“MACD当前为正值，但动能一致性仍待验证”。
若价格位于布林带中上部或高于部分均线，只能说明当前位置关系，不要写成“具备一定上行空间”“上方仍有空间”或其他空间判断。
输出前必须做一次逐词自检：最终报告中不得出现“站上”“站稳”“有效突破”“强势突破”“持续运行于”“持续放大”“突破布林带上轨”“上行空间”这些原词；若出现，必须全部改写后再输出。
在工具结果充分时，报告应保持足够展开，正常情况下不少于800字。

不要输出交易建议、目标价、价格区间、仓位或执行计划。
不得添加任何署名、作者、分析师、日期或声明信息。"""

    def _sanitize_report(self, report: str) -> str:
        if not isinstance(report, str) or not report:
            return report

        sanitized = report
        for pattern, replacement in _MARKET_REPORT_SANITIZE_RULES:
            sanitized = re.sub(pattern, replacement, sanitized)

        if sanitized != report:
            logger.info("[market_analyst_v2] 已对报告执行合规净化")

        return sanitized

    def _get_company_name(self, ticker: str, market_info: dict) -> str:
        """
        获取公司名称

        Args:
            ticker: 股票代码
            market_info: 市场信息

        Returns:
            公司名称
        """
        try:
            if market_info['is_china']:
                from tradingagents.dataflows.interface import get_china_stock_info_unified
                stock_info = get_china_stock_info_unified(ticker)
                if stock_info and "股票名称:" in stock_info:
                    return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            elif market_info['is_hk']:
                from tradingagents.dataflows.providers.hk.improved_hk import get_hk_company_name_improved
                return get_hk_company_name_improved(ticker)
            elif market_info['is_us']:
                us_stock_names = {
                    'AAPL': '苹果公司', 'TSLA': '特斯拉', 'NVDA': '英伟达',
                    'MSFT': '微软', 'GOOGL': '谷歌', 'AMZN': '亚马逊',
                }
                return us_stock_names.get(ticker.upper(), f"美股{ticker}")
        except Exception as e:
            logger.warning(f"获取公司名称失败: {e}")

        return f"股票{ticker}"
