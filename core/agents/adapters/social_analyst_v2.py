"""
社交媒体分析师 v2.0

基于AnalystAgent基类实现的社交媒体分析师
"""

import logging
from typing import Dict, Any, Optional

from langchain_core.messages import SystemMessage, HumanMessage

from core.agents.analyst import AnalystAgent
from core.agents.analyst import AnalystAgent
from core.agents.base import GENERIC_REPORT_FALLBACK
from core.agents.config import AgentMetadata, AgentCategory, LicenseTier, AgentInput, AgentOutput
from core.agents.registry import register_agent

logger = logging.getLogger(__name__)

# 尝试导入股票工具
try:
    from tradingagents.utils.stock_utils import StockUtils
except ImportError:
    logger.warning("无法导入StockUtils，部分功能可能不可用")
    StockUtils = None


@register_agent
class SocialMediaAnalystV2(AnalystAgent):
    """
    社交媒体分析师 v2.0
    
    功能：
    - 获取社交媒体情绪数据
    - 分析投资者情绪结构与市场热度
    - 识别情绪背离、噪音与待验证信号
    
    工作流程：
    1. 调用统一情绪工具获取社交媒体数据
    2. 使用LLM分析情绪趋势
    3. 生成社交媒体分析报告
    
    示例:
        from langchain_openai import ChatOpenAI
        from core.agents import create_agent

        llm = ChatOpenAI(model="gpt-4")
        agent = create_agent("social_analyst_v2", llm)

        result = agent.execute({
            "ticker": "AAPL",
            "analysis_date": "2024-12-15"
        })
    """

    # Agent元数据
    metadata = AgentMetadata(
        id="social_analyst_v2",
        name="社交媒体分析师 v2.0",
        description="分析社交媒体情绪，提炼热度变化、情绪背离与噪音风险",
        category=AgentCategory.ANALYST,
        version="2.0.0",
        license_tier=LicenseTier.FREE,
        default_tools=["get_stock_sentiment_unified"],
        inputs=[
            AgentInput(name="ticker", type="string", description="股票代码"),
            AgentInput(name="analysis_date", type="string", description="分析日期"),
        ],
        outputs=[
            AgentOutput(name="sentiment_report", type="string", description="社交媒体情绪分析报告"),
        ],
        requires_tools=True,
        output_field="sentiment_report",
        report_label="【社交媒体分析 v2】",
        workflow_stage="analyst",
    )

    # 分析师类型
    analyst_type = "social"
    
    # 输出字段名
    output_field = "sentiment_report"

    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """覆盖执行逻辑以支持专用情绪分析提示词。"""
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

            system_prompt = system_override or self._build_system_prompt(market_type, context=context, state=state)
            user_prompt = user_override or self._build_user_prompt(ticker, analysis_date, {}, state)
            analysis_prompt = analysis_override or self._build_analysis_prompt(ticker)

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            if self._llm:
                if self._langchain_tools:
                    report = self.invoke_with_tools(messages, analysis_prompt=analysis_prompt)
                else:
                    response = self._invoke_llm_with_trace(messages)
                    report = response.content if hasattr(response, "content") else str(response)
            else:
                raise ValueError("LLM not initialized")

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
        logger.info("🔍 [SocialAnalystV2] 开始构建系统提示词")
        
        if state is None:
            state = {}
        
        # 从 state 中提取必要的变量（如果系统提示词模板需要）
        # 注意：虽然系统提示词通常不需要变量，但某些模板可能需要 ticker、current_date 等
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        template_variables = {}
        
        # 如果 state 中有 ticker 和 analysis_date，提取它们（系统提示词模板可能需要）
        if "ticker" in state:
            template_variables["ticker"] = state["ticker"]
        if "analysis_date" in state or "trade_date" in state:
            analysis_date = state.get("analysis_date") or state.get("trade_date")
            if analysis_date:
                # 确保日期格式正确
                if isinstance(analysis_date, str) and len(analysis_date) > 10:
                    analysis_date = analysis_date.split()[0]
                template_variables["current_date"] = analysis_date
                template_variables["analysis_date"] = analysis_date
        
        # 使用基类的通用方法从模板系统获取提示词（参考 research_manager_v2）
        # 基类会自动从 state 中提取系统变量（如 current_price、industry 等）
        prompt = self._get_prompt_from_template(
            agent_type="analysts_v2",
            agent_name="social_analyst_v2",
            variables=template_variables,  # 传递必要的变量
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=context or state.get("context"),  # 优先使用传入的 context，否则从 state 获取
            fallback_prompt=None,
            prompt_type="system"  # 🔑 关键：明确指定获取系统提示词
        )
        
        logger.info(f"📝 系统提示词长度: {len(prompt)} 字符")

        if prompt:
            # 🔥 增强约束：明确要求如果没有数据就不要分析该维度
            data_constraint = """

## ⚠️ 数据缺失处理规则（重要）
**如果工具返回的数据中没有某个维度的数据，请遵循以下规则：**
1. **不要分析该维度**：如果数据中没有KOL观点、散户情绪、机构持仓等具体信息，就不要在报告中包含这些部分的分析
2. **或者明确说明数据缺失**：如果必须提及某个维度，请明确说明"该维度数据缺失，暂不分析"
3. **绝对禁止编造**：严禁在没有数据的情况下编造、假设或推测任何维度的分析内容
4. **只分析实际存在的数据**：仔细检查工具返回的数据，只分析数据中实际存在的维度

**示例**：如果工具返回的数据只有新闻情绪分析，没有KOL数据，则：
- ❌ 错误：编造"多位分析师指出..."、"部分KOL认为..."等不存在的内容
- ✅ 正确：跳过KOL观点汇总部分，或者说明"KOL数据缺失，暂不分析"
"""
            return prompt + data_constraint
        
        # 降级：使用默认提示词
        return f"""您是一位专业的社交媒体情绪分析师。

    您的职责是分析社交媒体上的投资者情绪结构、讨论热度和观点分歧，识别哪些情绪信号值得跟踪，哪些只是噪音。

    分析要点：
    1. 情绪方向与热度 - 讨论更偏乐观、悲观还是分歧加大
    2. 情绪来源结构 - 散户、主题社区、KOL 或机构观点分别在表达什么
    3. 情绪背离 - 情绪变化与基本面、价格行为是否一致
    4. 噪音识别 - 哪些说法缺乏证据、容易放大短期波动
    5. 后续观察信号 - 仍需跟踪的情绪变化、讨论主题和验证事件

    严格要求：
    - 不得输出买入、卖出、持有、加减仓、目标价、价格区间、止损止盈或仓位建议。
    - 允许引用工具返回的真实情绪指标、讨论热度和文本片段，但不得改写成执行性结论。

    请使用中文，基于真实数据进行分析。"""

    def _build_user_prompt(
        self,
        ticker: str,
        analysis_date: str,
        tool_data: Dict[str, Any],  # 保留参数以兼容基类，但工具数据会通过 ToolMessage 传递
        state: Dict[str, Any]
    ) -> str:
        """
        构建用户提示词（参考 research_manager_v2 和 fundamentals_analyst_v2 的实现）
        
        Args:
            ticker: 股票代码
            analysis_date: 分析日期
            tool_data: 工具返回的数据（保留以兼容基类，但工具数据会通过 ToolMessage 传递）
            state: 工作流状态（用于提取模板变量）
            
        Returns:
            用户提示词
        """
        logger.info("🔍 [SocialAnalystV2] 开始构建用户提示词")
        logger.info(f"📊 股票代码: {ticker}")
        logger.info(f"📅 分析日期: {analysis_date}")
        
        if state is None:
            state = {}
        
        # 获取公司名称和市场信息
        company_name = self._get_company_name(ticker, state)
        market_name = "中国A股"
        currency_name = "人民币"
        currency_symbol = "¥"
        
        if StockUtils and ticker:
            try:
                market_info = StockUtils.get_market_info(ticker)
                market_name = market_info.get('market_name', "中国A股")
                currency_name = market_info.get('currency_name', "人民币")
                currency_symbol = market_info.get('currency_symbol', "¥")
            except Exception as e:
                logger.warning(f"获取市场信息失败: {e}")
        
        # 准备模板变量（参考 research_manager_v2 的实现）
        # 🔑 关键：确保日期格式正确（YYYY-MM-DD），而不是 datetime 对象
        if isinstance(analysis_date, str):
            # 如果已经是字符串，确保格式正确
            if len(analysis_date) > 10:
                # 如果是 datetime 字符串（如 "2026-01-14 00:00:00"），只取日期部分
                analysis_date_str = analysis_date.split()[0]
            else:
                analysis_date_str = analysis_date
        else:
            # 如果是 datetime 对象，转换为字符串
            from datetime import datetime
            if isinstance(analysis_date, datetime):
                analysis_date_str = analysis_date.strftime("%Y-%m-%d")
            else:
                analysis_date_str = str(analysis_date)
        
        template_variables = {
            "ticker": ticker,
            "company_name": company_name,
            "market_name": market_name,
            "analysis_date": analysis_date_str,  # 🔑 确保是字符串格式 YYYY-MM-DD
            "current_date": analysis_date_str,  # 🔑 确保是字符串格式 YYYY-MM-DD
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
            agent_name="social_analyst_v2",
            variables=template_variables,
            state=state,  # 🔑 传递 state，基类会自动提取系统变量
            context=state.get("context"),  # 从 state 中获取 context
            fallback_prompt=None,
            prompt_type="user"  # 🔑 明确指定获取用户提示词
        )
        
        if prompt:
            logger.info(f"✅ 从模板系统获取社交媒体分析师 v2.0 用户提示词 (长度: {len(prompt)})")
            logger.info(f"📝 用户提示词前500字符:\n{prompt[:500]}...")
            return prompt
        
        # 降级：使用默认提示词（不再检查 tool_data，因为工具数据会通过 ToolMessage 传递）
        logger.warning("⚠️ 未从模板系统获取到用户提示词，使用默认提示词")
        # 🔑 关键：在默认提示词中明确告诉LLM要使用什么日期调用工具
        return f"""请对股票 {ticker}（{company_name}）进行详细的情绪研究：

**分析日期**：{analysis_date_str}

**重要提示**：调用工具 get_stock_sentiment_unified 时，必须使用 curr_date 参数，值为：{analysis_date_str}

    请调用工具获取社交媒体数据，然后基于真实结果输出中文研究报告，至少包含：
    1. 情绪方向、热度与主要讨论主题
    2. 情绪背离、观点分歧与潜在噪音来源
    3. 可能强化或削弱研究判断的情绪信号
    4. 需要继续跟踪的后续观察事项

    禁止输出买卖建议、目标价、价格区间、止损止盈、仓位计划或任何执行性指令。"""

    def _get_company_name(self, ticker: str, state: Dict[str, Any]) -> str:
        """获取公司名称"""
        company_name = str(
            state.get("company_name")
            or state.get("stock_name")
            or state.get("name")
            or ""
        )
        if company_name:
            return company_name
        
        # 使用StockUtils获取
        if StockUtils:
            try:
                market_info = StockUtils.get_market_info(ticker)
                if market_info.get('is_china'):
                    from tradingagents.dataflows.interface import get_china_stock_info_unified
                    stock_info = get_china_stock_info_unified(ticker)
                    if "股票名称:" in stock_info:
                        return stock_info.split("股票名称:")[1].split("\n")[0].strip()
            except Exception as e:
                logger.debug(f"获取公司名称失败: {e}")
        
        return f"股票{ticker}"

    def _build_analysis_prompt(self, ticker: str) -> str:
        """构建工具调用后的情绪分析提示词。"""
        return f"""基于获取的数据，请生成 {ticker} 的专业情绪研究报告，包括：

1. 情绪方向与热度
2. 观点结构与渠道差异
3. 情绪变化与分化
4. 噪音与风险
5. 对整体研究结论的影响
6. 后续观察事项

如果工具结果没有 KOL、散户、机构、平台分层、互动数据或高影响力消息等某个维度，就不要分析该维度；如必须提及，只能写“工具结果未提供”或“该维度暂不分析”。
如果工具明确说明当前结果来自新闻回退情绪摘要而非真实社媒内容，正文必须明确写出这一点，且不得把回退结果写成 KOL、散户、机构或社区分层结论。
情绪方向、讨论热度、平台分布、互动强弱和高影响力消息要分开表述；不要把消息数量更多、关键词更集中或互动更高，直接写成“市场一致看多”“情绪持续升温”“趋势确认”。
如果工具只提供当前快照、最近7天汇总或有限条消息，不得写“持续升温”“连续多日改善”“情绪已经反转”“市场形成一致预期”等需要更长时序验证的措辞。
如果高影响力消息与总体情绪统计不一致，必须写出这种分化及其对结论强度的限制。
可以引用工具返回的情绪评级、消息数量、平台分布、关键词、话题标签、互动数据和高影响力消息做事实说明，但不得把这些内容改写成目标价、价格区间、买卖建议、做多做空结论或执行计划。
请使用研究口径表达情绪含义，优先使用“偏积极”“偏审慎”“中性”“分化加大”“噪音较高”“一致性有限”“值得继续跟踪”等表述，不要使用“情绪拐点已至”“全面看多”“抄底情绪升温”“马上反转”等交易化措辞。
`## 对整体研究结论的影响` 只说明情绪信号如何强化、削弱或中性影响整体研究判断，不要把情绪直接写成趋势结论。
`## 后续观察事项` 只能写需要继续跟踪的情绪方向、讨论主题、平台结构变化、互动强度变化或与新闻/基本面的交叉验证，不得写成交易触发条件。
在工具结果充分时，报告应保持足够展开，正常情况下不少于700字。

不要输出投资建议、目标价、价格区间、仓位或执行计划。
不得添加任何署名、作者、分析师、日期或声明信息。"""

